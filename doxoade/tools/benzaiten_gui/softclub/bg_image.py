# -*- coding: utf-8 -*-
# doxoade/tools/benzaiten_gui/softclub/bg_image.py
"""
SOFTCLUB BG_IMAGE v14 — FrameStore determinístico + logger assíncrono.

Ma'at v14:
- chunking/aquecimento é por ASSINATURA DA FONTE (sig), não por frame:
  uma fonte => aquece os N frames UMA vez => marca DONE => nunca re-kicka;
- cada frame vira entrada de cache (sig, variant, i) + hash de conteúdo p/ inspeção;
- logger ASSÍNCRONO: _log() só enfileira; thread daemon drena em lote (não bloqueia render);
- recolor no small + upscale em C (Pillow) + interleave numpy.
"""
import json
import os
import struct
import subprocess
import sys
import threading
import time
import zlib
import hashlib
import collections
from pathlib import Path

try:
    from PIL import Image
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False
try:
    import numpy as _np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

_FRAME_W, _FRAME_H = 480, 270
QUAL = {'low': (240, 135), 'full': (480, 270)}
_MAX_FRAMES = 24

_PROC = None
_SRC_SIG = None
_FULL_CACHE = {}
_RECOLOR_CACHE = {}          # (sig, variant, i) -> bytes BGRA
_FRAME_HASH = {}          # (sig, variant, i) -> hash8
_DONE_VARIANTS = set()    # (sig, variant) já aquecido por completo
_PENDING = set()          # (sig, variant) em aquecimento
_FAILED = set()
_LOCK = threading.Lock()
_PROC_LOCK = threading.Lock()
_PS_LOCK = threading.Lock()
_REPAINT = None
_ANIM = None
_frame_idx = 0

# ── LOGGER ASSÍNCRONO (não bloqueia o render) ────────────────────
_LOG_Q = collections.deque()
_LOG_ON = os.environ.get('SOFTCLUB_DEBUG') == '1'
_LOG_STARTED = False

def _ensure_pump():
    global _LOG_STARTED
    if not _LOG_STARTED:
        _LOG_STARTED = True
        threading.Thread(target=_log_pump, daemon=True).start()

def render_full(W, H, variant='day'):
    """Não-bloqueante: fade ativo > melhor frame > None (agenda staircase)."""
    fb = _FADE_BUF.get('buf')
    if fb is not None and fb[1] == W and fb[2] == H:
        _LAST_PRESENTED = (fb[0], W, H)
        return (fb[0], W, H)
    proc = get_processed()
    if not proc:
        return None
    sig = _SRC_SIG
    n = len(proc[2])
    if n > 1:
        _ensure_animator()
    seq = _pp_sequence(n)
    fi = seq[_frame_idx % len(seq)]
    res = _best_frame(sig, variant, fi)
    if res:
        b, (bw, bh) = res
        _LAST_PRESENTED = (b, bw, bh)
        return (b, bw, bh)
    _ensure_staircase(sig, variant)
    return None

def _log_pump():
    while True:
        time.sleep(0.25)
        if _LOG_Q:
            lines = []
            while _LOG_Q:
                try:
                    lines.append(_LOG_Q.popleft())
                except IndexError:
                    break
            if lines:
                sys.stderr.write("\n".join(lines) + "\n")
                sys.stderr.flush()

def _log(msg):
    global _LOG_STARTED
    if not _LOG_ON:
        return
    _LOG_Q.append(f"[BG_IMAGE] {msg}")
    if not _LOG_STARTED:
        _LOG_STARTED = True
        threading.Thread(target=_log_pump, daemon=True).start()


def _logp(msg):
    """Progresso de degraus: sempre visível, assíncrono (não bloqueia)."""
    _LOG_Q.append(f"[BG_IMAGE] {msg}")
    _ensure_pump()

_PREFS_BG = None

def set_prefs_bg(path):
    """Tier 3 (prefs): fundo persistido; só aceita se existir no disco (Q2)."""
    global _PREFS_BG
    if not path:
        _PREFS_BG = None
        return False
    p = Path(str(path)).expanduser()
    if p.suffix.lower() in _OK_EXT and p.exists():
        _PREFS_BG = str(p)
        return True
    _PREFS_BG = None  # bg sumiu: cai no procedural, prefs intacto
    return False

def wanted_bg_path():
    if _OVERRIDE:
        return _OVERRIDE
    v = (os.environ.get('SOFTCLUB_BG', '') or '').strip()
    v = v.strip('"').strip("'").strip()
    if v:
        return v
    return _PREFS_BG

_OVERRIDE = None


def custom_active():
    return wanted_bg_path() is not None


def set_repaint_fn(fn):
    global _REPAINT
    _REPAINT = fn


def set_bg_path(path):
    global _OVERRIDE, _PROC, _SRC_SIG, _frame_idx
    p = Path(str(path)).expanduser()
    if p.suffix.lower() not in _OK_EXT or not p.exists():
        return False
    _OVERRIDE = str(p)
    _PROC = None
    _SRC_SIG = None
    _frame_idx = 0
    _FULL_CACHE.clear()
    _FRAME_HASH.clear()
    _DONE_VARIANTS.clear()
    _FAILED.clear()
    with _LOCK:
        _PENDING.clear()
    _log(f'bg override: {p.name}')
    return True

_OK_EXT = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp'}
_LAST_PRESENTED = None
_FADE_BUF = {'buf': None}
_FADE_GEN = {'g': 0}

def note_presented(bgra, w, h):
    """Registra o último buffer apresentado (p/ crossfade desde procedural)."""
    global _LAST_PRESENTED
    _LAST_PRESENTED = (bgra, w, h)

def fade_to_path(path, W, H, variant='night', steps=12, secs=0.6):
    """Crossfade assíncrono p/ nova fonte; sem numpy = switch seco (fail-graceful)."""
    if not set_bg_path(path):
        return False
    threading.Thread(target=_fade_job, args=(W, H, variant, steps, secs),
                     daemon=True).start()
    return True

def _fade_job(W, H, variant, steps, secs):
    _FADE_GEN['g'] += 1
    gen = _FADE_GEN['g']
    old = _LAST_PRESENTED
    proc = get_processed()
    if not proc:
        return
    sig = _SRC_SIG
    _render_one(proc, sig, variant, 0, 'low')
    _render_one(proc, sig, variant, 0, 'full')
    new = (_FULL_CACHE.get((sig, variant, 'full', 0))
           or _FULL_CACHE.get((sig, variant, 'low', 0)))
    if (old is None or new is None or old[1] != W or old[2] != H
            or len(old[0]) != len(new) or not HAS_NUMPY):
        _FADE_BUF['buf'] = None
        if _REPAINT:
            _REPAINT()
        return
    a = _np.frombuffer(old[0], dtype=_np.uint16)
    b = _np.frombuffer(new, dtype=_np.uint16)
    for s in range(1, steps + 1):
        if _FADE_GEN['g'] != gen:
            return
        t = (s * 256) // steps
        m = ((a * (256 - t)) + (b * t)) >> 8
        _FADE_BUF['buf'] = (m.clip(0, 255).astype(_np.uint8).tobytes(), W, H)
        if _REPAINT:
            _REPAINT()
        time.sleep(secs / steps)
    _FADE_BUF['buf'] = None
    if _REPAINT:
        _REPAINT()

# ── decoders ─────────────────────────────────────────────────────
def _decode_png(data):
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('não é PNG')
    pos, w, h, color, idat = 8, 0, 0, 0, bytearray()
    while pos + 8 <= len(data):
        ln = struct.unpack('>I', data[pos:pos + 4])[0]
        ctype = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + ln]
        if ctype == b'IHDR':
            w, h, depth, color, _, _, inter = struct.unpack('>IIBBBBB', chunk)
            if depth != 8 or inter != 0 or color not in (2, 6):
                raise ValueError('PNG não suportado')
        elif ctype == b'IDAT':
            idat += chunk
        elif ctype == b'IEND':
            break
        pos += 12 + ln
    ch = 3 if color == 2 else 4
    stride = w * ch
    raw = zlib.decompress(bytes(idat))
    px = bytearray(w * h * ch)
    prev = bytearray(stride)
    p = 0
    for y in range(h):
        f = raw[p]; p += 1
        line = bytearray(raw[p:p + stride]); p += stride
        if f == 1:
            for i in range(ch, stride):
                line[i] = (line[i] + line[i - ch]) & 255
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif f == 3:
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 255
        elif f == 4:
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                b = prev[i]
                c = prev[i - ch] if i >= ch else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 255
        px[y * stride:(y + 1) * stride] = line
        prev = line
    return w, h, ch, bytes(px)


def _thumb_via_pillow_frames(p, tw, th):
    im = Image.open(p)
    n = getattr(im, 'n_frames', 1)
    if n > 1:
        want = min(n, _MAX_FRAMES)
        idxs = sorted(set(int(i * n / want) for i in range(want)))
    else:
        idxs = [0]
    smalls, delays = [], []
    for i in idxs:
        try:
            im.seek(i)
        except EOFError:
            break
        fr = im.convert('RGB').resize((tw, th), Image.Resampling.LANCZOS)
        smalls.append(bytes(fr.tobytes()))
        d = im.info.get('duration') or 100
        delays.append(max(40, min(500, int(d))))
    return smalls, delays


def _thumb_via_powershell(src, out_png, tw, th):
    ps = ("Add-Type -AssemblyName System.Drawing;"
          f"$s = [System.Drawing.Image]::FromFile('{src}');"
          f"$b = New-Object System.Drawing.Bitmap($s, {tw}, {th});"
          f"$b.Save('{out_png}', [System.Drawing.Imaging.ImageFormat]::Png);"
          "$b.Dispose(); $s.Dispose()")
    subprocess.run(['powershell', '-NoProfile', '-command', ps],
                   capture_output=True, timeout=30, check=True)


def _thumb_via_wic(src, out_png, tw, th):
    ps = ("Add-Type -AssemblyName PresentationCore;"
          "$u = [System.Uri]::new('" + src + "');"
          "$d = [System.Windows.Media.Imaging.BitmapDecoder]::Create($u,"
          "[System.Windows.Media.Imaging.BitmapCreateOptions]::None,"
          "[System.Windows.Media.Imaging.BitmapCacheOption]::OnLoad);"
          "$f = $d.Frames[0];"
          "$sx = %d / $f.PixelWidth; $sy = %d / $f.PixelHeight;"
          "$t = New-Object System.Windows.Media.Imaging.TransformedBitmap($f,"
          "(New-Object System.Windows.Media.ScaleTransform($sx, $sy)));"
          "$e = New-Object System.Windows.Media.Imaging.PngBitmapEncoder;"
          "$e.Frames.Add([System.Windows.Media.Imaging.BitmapFrame]::Create($t));"
          "$o = [System.IO.File]::Create('" + out_png + "'); $e.Save($o); $o.Close()") % (tw, th)
    subprocess.run(['powershell', '-NoProfile', '-command', ps],
                   capture_output=True, timeout=30, check=True)


def _area_downscale(w, h, ch, px, tw, th):
    out = bytearray(tw * th * 3)
    for ty in range(th):
        y0 = ty * h // th
        y1 = max(y0 + 1, (ty + 1) * h // th)
        for tx in range(tw):
            x0 = tx * w // tw
            x1 = max(x0 + 1, (tx + 1) * w // tw)
            rs = gs = bs = n = 0
            for yy in range(y0, y1):
                base = yy * w * ch
                for xx in range(x0, x1):
                    i = base + xx * ch
                    rs += px[i]; gs += px[i + 1]; bs += px[i + 2]; n += 1
            o = (ty * tw + tx) * 3
            out[o] = rs // n; out[o + 1] = gs // n; out[o + 2] = bs // n
    return out


def _box_blur3(tw, th, buf):
    src = bytes(buf)
    ba = bytearray(buf)
    for y in range(1, th - 1):
        for x in range(1, tw - 1):
            o = (y * tw + x) * 3
            for k in range(3):
                s = 0
                for dy in (-1, 0, 1):
                    rb = (y + dy) * tw * 3
                    for dx in (-1, 0, 1):
                        s += src[rb + (x + dx) * 3 + k]
                ba[o + k] = s // 9
    return bytes(ba)


def _extract_palette(small):
    buckets = {}
    rs = gs = bs = 0
    n = len(small) // 3
    for i in range(0, len(small), 3):
        r = small[i]; g = small[i + 1]; b = small[i + 2]
        rs += r; gs += g; bs += b
        e = buckets.setdefault((r >> 5, g >> 5, b >> 5), [0, 0, 0, 0])
        e[0] += 1; e[1] += r; e[2] += g; e[3] += b
    top = sorted(buckets.values(), key=lambda e: -e[0])[:6]
    dom = [[e[1] // e[0], e[2] // e[0], e[3] // e[0]] for e in top]
    vib = max(dom, key=lambda c: max(c) - min(c)) if dom else [0, 0, 0]
    return {'avg': [rs // n, gs // n, bs // n], 'dominant': dom, 'vibrant': vib}


def _ramp_for(variant):
    if variant == 'night':
        lo, hi = (16, 18, 26), (96, 104, 124)
        sat = 0.60
    else:
        lo, hi = (88, 108, 142), (206, 220, 238)
        sat = 0.50
    lut = bytearray(256 * 3)
    for L in range(256):
        t = L / 255.0
        s = t * t * (3.0 - 2.0 * t)
        t = 0.5 * t + 0.5 * s
        for i in range(3):
            lut[L * 3 + i] = int(lo[i] + (hi[i] - lo[i]) * t)
    return bytes(lut), sat


def _recolor_rgb(rgb, tw, th, variant):
    lut3, sat = _ramp_for(variant)
    out = bytearray(len(rgb))
    for i in range(0, len(rgb), 3):
        cr, cg, cb = rgb[i], rgb[i + 1], rgb[i + 2]
        L = (cr * 299 + cg * 587 + cb * 114) // 1000
        j = L * 3
        br, bg_, bb = lut3[j], lut3[j + 1], lut3[j + 2]
        v = br + sat * (cr - L)
        out[i] = 0 if v < 0 else (255 if v > 255 else int(v))
        v = bg_ + sat * (cg - L)
        out[i + 1] = 0 if v < 0 else (255 if v > 255 else int(v))
        v = bb + sat * (cb - L)
        out[i + 2] = 0 if v < 0 else (255 if v > 255 else int(v))
    return bytes(out)


def _small_to_bgra(rgb_small, tw, th, W, H):
    if HAS_PILLOW:
        im = Image.frombytes('RGB', (tw, th), rgb_small)
        im = im.resize((W, H), Image.Resampling.BILINEAR)
        rgb = im.tobytes()
    else:
        rgb = _nearest_rgb(rgb_small, tw, th, W, H)
    if HAS_NUMPY:
        a = _np.frombuffer(rgb, dtype=_np.uint8).reshape(H, W, 3)
        b = _np.empty((H, W, 4), dtype=_np.uint8)
        b[..., 0] = a[..., 2]; b[..., 1] = a[..., 1]; b[..., 2] = a[..., 0]
        b[..., 3] = 255
        return b.tobytes()
    out = bytearray(W * H * 4)
    o = 0
    for i in range(0, len(rgb), 3):
        out[o] = rgb[i + 2]; out[o + 1] = rgb[i + 1]; out[o + 2] = rgb[i]
        out[o + 3] = 255
        o += 4
    return bytes(out)


def _nearest_rgb(rgb_small, tw, th, W, H):
    out = bytearray(W * H * 3)
    for y in range(H):
        sy = min(th - 1, y * th // H)
        srow = sy * tw * 3
        orow = y * W * 3
        for x in range(W):
            sx = min(tw - 1, x * tw // W)
            si = srow + sx * 3
            out[orow + x * 3] = rgb_small[si]
            out[orow + x * 3 + 1] = rgb_small[si + 1]
            out[orow + x * 3 + 2] = rgb_small[si + 2]
    return bytes(out)


def _cache_dir():
    from doxoade.tools.filesystem import _find_project_root
    return Path(_find_project_root(os.getcwd())) / '.doxoade' / 'benzaiten' / 'softclub'


def _base_name(p, st):
    return f"img_{p.stem}_{st.st_mtime_ns}_{st.st_size}"


def get_processed():
    """Lazy singleton (tw, th, [smalls], palette, delays) + _SRC_SIG."""
    global _PROC, _SRC_SIG
    if _PROC:
        return _PROC
    with _PROC_LOCK:
        if _PROC:
            return _PROC
        path = wanted_bg_path()
        if not path:
            return None
        p = Path(path).expanduser()
        if not p.exists() or str(p) in _FAILED:
            return None
        try:
            st = p.stat()
            _SRC_SIG = hashlib.md5(f"{p}:{st.st_mtime_ns}:{st.st_size}".encode()).hexdigest()[:12]
            base = _base_name(p, st)
            cdir = _cache_dir()
            cdir.mkdir(parents=True, exist_ok=True)
            meta_f = cdir / (base + '_meta13.json')
            smalls, delays = [], []
            if meta_f.exists():
                meta = json.loads(meta_f.read_text(encoding='utf-8'))
                ok = True
                for i in range(meta.get('frames', 1)):
                    sf = cdir / (base + f'_s13_{i}.raw')
                    if sf.exists() and sf.stat().st_size == meta['tw'] * meta['th'] * 3:
                        smalls.append(sf.read_bytes())
                        delays.append(meta.get('delays', [100])[i] if i < len(meta.get('delays', [])) else 100)
                    else:
                        ok = False
                        break
                if not ok:
                    smalls, delays = [], []
            if smalls:
                _log(f'lazy: cache hit ({len(smalls)} frame(s))')
                _PROC = (meta['tw'], meta['th'], smalls, meta.get('palette'), delays)
                return _PROC
            tw, th = 96, 72
            if HAS_PILLOW:
                try:
                    smalls, delays = _thumb_via_pillow_frames(p, tw, th)
                    _log(f'decoder pillow ok: {p.name} ({len(smalls)} frame(s))')
                except Exception as e:
                    _log(f'decoder pillow falhou: {e}')
            if not smalls:
                data = None
                tmp = cdir / (base + '_tmp.png')
                for nome, dec in (('wic', _thumb_via_wic), ('gdi', _thumb_via_powershell)):
                    try:
                        with _PS_LOCK:
                            dec(str(p), str(tmp), tw, th)
                        data = _decode_png(tmp.read_bytes())
                        _log(f'decoder {nome} ok: {p.name}')
                        break
                    except Exception as e:
                        _log(f'decoder {nome} falhou: {e}')
                if data is None and p.suffix.lower() == '.png':
                    data = _decode_png(p.read_bytes())
                if data is None:
                    _FAILED.add(str(p))
                    _log('sem decoder; fallback procedural (memorizado)')
                    return None
                w, h, ch, px = data
                one = px if (ch == 3 and w == tw and h == th) else \
                    _area_downscale(w, h, ch, px, tw, th)
                smalls, delays = [bytes(one)], [100]
            blurred = []
            for s in smalls:
                b = _box_blur3(tw, th, s)
                b = _box_blur3(tw, th, b)
                blurred.append(b)
            palette = _extract_palette(blurred[0])
            for i, b in enumerate(blurred):
                (cdir / (base + f'_s13_{i}.raw')).write_bytes(b)
            meta_f.write_text(json.dumps(
                {'tw': tw, 'th': th, 'frames': len(blurred),
                 'delays': delays, 'palette': palette},
                ensure_ascii=False), encoding='utf-8')
            _log(f'lazy: processado 1x ({base}) frames={len(blurred)}')
            _PROC = (tw, th, blurred, palette, delays)
            return _PROC
        except Exception as e:
            _FAILED.add(str(p))
            _log(f'erro: {e} (memorizado)')
            return None


def get_image_palette():
    return _PROC[3] if _PROC else None


def _pp_sequence(n):
    if n <= 2:
        return list(range(n))
    return list(range(n)) + list(range(n - 2, 0, -1))


def _ensure_animator():
    """Thread daemon: avança _frame_idx (ping-pong); repaint só via fn
    thread-safe (InvalidateRect). Throttle 20fps; loop à prova de morte."""
    global _ANIM
    with _LOCK:
        if _ANIM is not None:
            return
        _ANIM = 'boot'
    def loop():
        global _frame_idx
        last = 0.0
        while True:
            try:
                proc = _PROC
                n = len(proc[2]) if proc else 0
                if n < 2:
                    time.sleep(0.30)
                    continue
                seq = _pp_sequence(n)
                _frame_idx = (_frame_idx + 1) % len(seq)
                fi = seq[_frame_idx % len(seq)]
                now = time.time()
                if _REPAINT and (now - last) >= 0.066:
                    last = now
                    try:
                        _REPAINT()
                    except Exception:
                        pass
                try:
                    d = max(0.04, min(0.5, proc[4][fi % len(proc[4])] / 1000.0))
                except Exception:
                    d = 0.10
                time.sleep(d)
            except Exception:
                time.sleep(0.25)
    t = threading.Thread(target=loop, daemon=True)
    t.start()
    _ANIM = t

_SAT_BOOST = {'day': 0.22, 'night': 0.08}
_CHROMA_MIX = {'day': 0.30, 'night': 0.15}

def _cl255(v):
    return 0 if v < 0 else (255 if v > 255 else int(v))

def _recolor_v18(small, tw, th, variant):
    """Recolor legível + croma de volta (day vivo, night sóbrio).
    Fast-path numpy: boost de saturação + hue original capado (f<=1.75)."""
    boost = _SAT_BOOST.get(variant, 0.0)
    mix = _CHROMA_MIX.get(variant, 0.0)
    base = _recolor_rgb(small, tw, th, variant)
    if boost <= 0.0 and mix <= 0.0:
        return base
    if HAS_NUMPY:
        b = _np.frombuffer(base, dtype=_np.uint8).reshape(-1, 3).astype(_np.int32)
        if boost > 0.0:
            m = b.mean(axis=1, keepdims=True)
            b = m + (b - m) * (1.0 + boost)
        if mix > 0.0:
            s = _np.frombuffer(small, dtype=_np.uint8).reshape(-1, 3).astype(_np.int32)
            W_ = _np.array([299, 587, 114])
            L = (s @ W_) // 1000
            Lt = (_np.clip(b, 0, 255) @ W_) // 1000
            f = _np.where(L > 4, _np.minimum(1.75, Lt / _np.maximum(L, 1)), 0.0)
            hue = _np.where((L > 4)[:, None], _np.minimum(255, s * f[:, None]), Lt[:, None])
            b = b + (hue - b) * mix
        return _np.clip(b, 0, 255).astype(_np.uint8).tobytes()
    out = bytearray(len(base))
    for i in range(0, len(base), 3):
        r, g, b2 = base[i], base[i + 1], base[i + 2]
        if boost > 0.0:
            m = (r + g + b2) / 3.0
            r += (r - m) * boost; g += (g - m) * boost; b2 += (b2 - m) * boost
        if mix > 0.0:
            o_r, o_g, o_b = small[i], small[i + 1], small[i + 2]
            L = (o_r * 299 + o_g * 587 + o_b * 114) // 1000
            Lt = (max(0, min(255, r)) * 299 + max(0, min(255, g)) * 587 + max(0, min(255, b2)) * 114) // 1000
            if L > 4:
                f = min(1.75, Lt / L)
                hr, hg, hb = min(255, o_r * f), min(255, o_g * f), min(255, o_b * f)
            else:
                hr = hg = hb = Lt
            r += (hr - r) * mix; g += (hg - g) * mix; b2 += (hb - b2) * mix
        out[i] = _cl255(r); out[i + 1] = _cl255(g); out[i + 2] = _cl255(b2)
    return bytes(out)

def _render_one(proc, sig, variant, i, qual):
    """Renderiza 1 frame na qualidade pedida; cacheia; cede GIL."""
    tw, th, smalls, _pal, _del = proc
    key = (sig, variant, qual, i)
    if key in _FULL_CACHE:
        return _FULL_CACHE[key]
    rec = _RECOLOR_CACHE.get((sig, variant, i))
    if rec is None:
        rec = _recolor_v18(smalls[i], tw, th, variant)
        _RECOLOR_CACHE[(sig, variant, i)] = rec
    W, H = QUAL[qual]
    b = _small_to_bgra(rec, tw, th, W, H)
    with _LOCK:
        _FULL_CACHE[key] = b
        while len(_FULL_CACHE) > 64:
            _FULL_CACHE.pop(next(iter(_FULL_CACHE)))
    return b


def _best_frame(sig, variant, i):
    """Melhor buffer disponível p/ o frame i (full > low > frame0)."""
    for qual in ('full', 'low'):
        hit = _FULL_CACHE.get((sig, variant, qual, i))
        if hit:
            return hit, QUAL[qual]
    for qual in ('full', 'low'):
        hit = _FULL_CACHE.get((sig, variant, qual, 0))
        if hit:
            return hit, QUAL[qual]
    return None


_STAIR = set()

def _ensure_staircase(sig, variant):
    with _LOCK:
        if (sig, variant) in _STAIR or (sig, variant) in _DONE_VARIANTS:
            return
        _STAIR.add((sig, variant))

    def job():
        try:
            proc = get_processed()
            if not proc:
                return
            n = len(proc[2])
            order = list(range(n))
            q = max(1, n // 4); h = max(1, n // 2)
            stages = [
                ('low', [0]), ('low', order[:q]), ('low', order[:h]), ('low', order),
                ('full', [0]), ('full', order[:q]), ('full', order),
            ]
            for qual, idxs in stages:
                _logp(f'degrau {qual}: {len(idxs)}/{n} frames')
                for i in idxs:
                    _render_one(proc, sig, variant, i, qual)
                    time.sleep(0.0)          # yield GIL p/ UI respirar
                if qual == 'full':
                    time.sleep(0.002)
                if _REPAINT:
                    try:
                        _REPAINT()
                    except Exception:
                        pass
            with _LOCK:
                _DONE_VARIANTS.add((sig, variant))
            hashes = ' '.join(
                f"f{i}:{hashlib.md5(_FULL_CACHE[(sig, variant, 'full', i)]).hexdigest()[:8]}"
                for i in order)
            _logp(f'staircase done sig={sig} {hashes}')
        except Exception as e:
            _log(f'staircase erro: {e}')
        finally:
            with _LOCK:
                _STAIR.discard((sig, variant))

    threading.Thread(target=job, daemon=True).start()


def process_async(W, H, variant='day', repaint_fn=None):
    if repaint_fn:
        set_repaint_fn(repaint_fn)
    render_full(W, H, variant)
    return True


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('uso: python -m doxoade.tools.benzaiten_gui.softclub.bg_image <imagem>')
        raise SystemExit(1)
    os.environ['SOFTCLUB_BG'] = sys.argv[1]
    _LOG_ON = True
    proc = get_processed()
    if not proc:
        print('falha ao processar imagem')
        raise SystemExit(2)
    print(json.dumps({'frames': len(proc[2]), 'delays': proc[4],
                      'palette': proc[3]}, indent=2))
