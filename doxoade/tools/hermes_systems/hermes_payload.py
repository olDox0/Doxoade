# doxoade/tools/hermes_systems/hermes_payload.py
"""
Hermes Custom Payload Serializer (HBC6-P2)
==========================================
Substitui o marshal.dumps() do CPython para reduzir drasticamente o tamanho do payload.
Técnicas: String Interning Pool, Vetores de Nomes, Serialização Estrutural.
"""
import struct
import types

# Tags de Tipo para o Constant Pool
TAG_NONE = 0
TAG_BOOL = 1
TAG_INT = 2
TAG_FLOAT = 3
TAG_STRING_REF = 4
TAG_BYTES = 5
TAG_TUPLE = 6
TAG_CODE_REF = 7
TAG_ELLIPSIS = 8
TAG_COMPLEX = 9
TAG_FROZENSET = 10

class StringPool:
    """Pool de Strings com Interning (Deduplicação O(1))."""
    def __init__(self):
        self.strings = []
        self.index_map = {}
        
    def intern(self, s: str) -> int:
        if not isinstance(s, str):
            raise TypeError(f"StringPool expected str, got {type(s)}")
        if s in self.index_map:
            return self.index_map[s]
        idx = len(self.strings)
        if idx > 0xFFFF:
            raise OverflowError("StringPool exceeded 65535 unique strings")
        self.strings.append(s)
        self.index_map[s] = idx
        return idx
        
    def serialize(self) -> bytes:
        buf = bytearray()
        buf += struct.pack('<I', len(self.strings))
        for s in self.strings:
            encoded = s.encode('utf-8')
            buf += struct.pack('<H', len(encoded))
            buf += encoded
        return bytes(buf)
        
    @classmethod
    def deserialize(cls, data: bytes, offset: int) -> tuple['StringPool', int]:
        pool = cls()
        count = struct.unpack_from('<I', data, offset)[0]
        offset += 4
        for _ in range(count):
            length = struct.unpack_from('<H', data, offset)[0]
            offset += 2
            s = data[offset:offset+length].decode('utf-8')
            offset += length
            pool.intern(s)
        return pool, offset

# ═══════════════════════════════════════════════════════════════════════════════
# EXTRAÇÃO (Alimenta o Pool antes de serializar)
# ═══════════════════════════════════════════════════════════════════════════════
def extract_strings(code_obj: types.CodeType, pool: StringPool):
    """Varre o CodeObject recursivamente e alimenta o StringPool."""
    for name in code_obj.co_names: pool.intern(name)
    for name in code_obj.co_varnames: pool.intern(name)
    for name in code_obj.co_freevars: pool.intern(name)
    for name in code_obj.co_cellvars: pool.intern(name)
    
    pool.intern(code_obj.co_filename)
    pool.intern(code_obj.co_name)
    pool.intern(code_obj.co_qualname)
    
    for const in code_obj.co_consts:
        _extract_const_strings(const, pool)

def _extract_const_strings(const, pool: StringPool):
    if isinstance(const, str): pool.intern(const)
    elif isinstance(const, (tuple, frozenset)):
        for item in const: _extract_const_strings(item, pool)
    elif isinstance(const, types.CodeType):
        extract_strings(const, pool)

# ═══════════════════════════════════════════════════════════════════════════════
# SERIALIZAÇÃO (Compressor)
# ═══════════════════════════════════════════════════════════════════════════════
def serialize_payload(co: types.CodeType) -> bytes:
    """Gera o payload binário customizado (HBC6-P2)."""
    pool = StringPool()
    extract_strings(co, pool)
    
    buf = bytearray()
    buf += pool.serialize()
    buf += serialize_code_obj(co, pool)
    return bytes(buf)

def serialize_code_obj(co: types.CodeType, pool: StringPool) -> bytes:
    buf = bytearray()
    # 1. Metadados (Inclui nlocals para reconstrução exata)
    buf += struct.pack('<HHHHH', co.co_argcount, co.co_posonlyargcount, 
                       co.co_kwonlyargcount, co.co_nlocals, co.co_stacksize)
    buf += struct.pack('<II', co.co_flags, co.co_firstlineno)
    
    # 2. Bytecode
    buf += struct.pack('<I', len(co.co_code))
    buf += co.co_code
    
    # 3. Constantes
    consts_buf = serialize_consts(co.co_consts, pool)
    buf += struct.pack('<I', len(consts_buf))
    buf += consts_buf
    
    # 4. Vetores de Nomes (uint16 IDs)
    buf += serialize_name_vector(co.co_names, pool)
    buf += serialize_name_vector(co.co_varnames, pool)
    buf += serialize_name_vector(co.co_freevars, pool)
    buf += serialize_name_vector(co.co_cellvars, pool)
    
    # 5. Tabelas de Linha e Exceção
    buf += struct.pack('<I', len(co.co_linetable))
    buf += co.co_linetable
    buf += struct.pack('<I', len(co.co_exceptiontable))
    buf += co.co_exceptiontable
    
    # 6. Strings do CodeObject
    buf += struct.pack('<HHH', pool.intern(co.co_filename), 
                       pool.intern(co.co_name), pool.intern(co.co_qualname))
    return bytes(buf)

def serialize_name_vector(names: tuple, pool: StringPool) -> bytes:
    buf = bytearray()
    buf += struct.pack('<H', len(names))
    for name in names:
        buf += struct.pack('<H', pool.intern(name))
    return bytes(buf)

def serialize_consts(consts: tuple, pool: StringPool) -> bytes:
    buf = bytearray()
    buf += struct.pack('<H', len(consts))
    for c in consts:
        if c is None: buf += struct.pack('<B', TAG_NONE)
        elif c is Ellipsis: buf += struct.pack('<B', TAG_ELLIPSIS)
        elif isinstance(c, bool): buf += struct.pack('<BB', TAG_BOOL, 1 if c else 0)
        elif isinstance(c, int):
            buf += struct.pack('<B', TAG_INT)
            if c == 0:
                buf += struct.pack('<H', 0)
            else:
                val_bytes = c.to_bytes((c.bit_length() + 8) // 8, 'little', signed=True)
                buf += struct.pack('<H', len(val_bytes))
                buf += val_bytes
        elif isinstance(c, float): buf += struct.pack('<Bd', TAG_FLOAT, c)
        elif isinstance(c, complex): buf += struct.pack('<Bdd', TAG_COMPLEX, c.real, c.imag)
        elif isinstance(c, str): buf += struct.pack('<BH', TAG_STRING_REF, pool.intern(c))
        elif isinstance(c, bytes):
            buf += struct.pack('<BI', TAG_BYTES, len(c))
            buf += c
        elif isinstance(c, tuple):
            buf += struct.pack('<B', TAG_TUPLE)
            buf += serialize_consts(c, pool)
        elif isinstance(c, frozenset):
            buf += struct.pack('<B', TAG_FROZENSET)
            buf += serialize_consts(tuple(c), pool)
        elif isinstance(c, types.CodeType):
            buf += struct.pack('<B', TAG_CODE_REF)
            code_bytes = serialize_code_obj(c, pool)
            buf += struct.pack('<I', len(code_bytes))
            buf += code_bytes
        else:
            raise TypeError(f"Unsupported constant type: {type(c)}")
    return bytes(buf)

# ═══════════════════════════════════════════════════════════════════════════════
# DESSERIALIZAÇÃO (Loader / Fallback Python)
# ═══════════════════════════════════════════════════════════════════════════════
def deserialize_payload(data: bytes) -> types.CodeType:
    offset = 0
    pool, offset = StringPool.deserialize(data, offset)
    co, offset = deserialize_code_obj(data, offset, pool)
    return co

def deserialize_code_obj(data: bytes, offset: int, pool: StringPool) -> tuple[types.CodeType, int]:
    argcount, posonly, kwonly, nlocals, stacksize = struct.unpack_from('<HHHHH', data, offset)
    offset += 10
    flags, firstlineno = struct.unpack_from('<II', data, offset)
    offset += 8
    
    code_len = struct.unpack_from('<I', data, offset)[0]
    offset += 4
    code = data[offset:offset+code_len]
    offset += code_len
    
    consts_len = struct.unpack_from('<I', data, offset)[0]
    offset += 4
    consts, offset = deserialize_consts(data, offset, offset + consts_len, pool)
    
    names, offset = deserialize_name_vector(data, offset, pool)
    varnames, offset = deserialize_name_vector(data, offset, pool)
    freevars, offset = deserialize_name_vector(data, offset, pool)
    cellvars, offset = deserialize_name_vector(data, offset, pool)
    
    linetable_len = struct.unpack_from('<I', data, offset)[0]
    offset += 4
    linetable = data[offset:offset+linetable_len]
    offset += linetable_len
    
    exctable_len = struct.unpack_from('<I', data, offset)[0]
    offset += 4
    exctable = data[offset:offset+exctable_len]
    offset += exctable_len
    
    filename_idx, name_idx, qualname_idx = struct.unpack_from('<HHH', data, offset)
    offset += 6
    
    # Reconstrução do CodeObject (Python 3.11+)
    co = types.CodeType(
        argcount, posonly, kwonly, nlocals, stacksize, flags,
        code, tuple(consts), tuple(names), tuple(varnames),
        pool.strings[filename_idx], pool.strings[name_idx], pool.strings[qualname_idx],
        firstlineno, linetable, exctable, tuple(freevars), tuple(cellvars)
    )
    return co, offset

def deserialize_name_vector(data: bytes, offset: int, pool: StringPool) -> tuple[list, int]:
    count = struct.unpack_from('<H', data, offset)[0]
    offset += 2
    names = []
    for _ in range(count):
        idx = struct.unpack_from('<H', data, offset)[0]
        offset += 2
        names.append(pool.strings[idx])
    return names, offset

def deserialize_consts(data: bytes, offset: int, end: int, pool: StringPool) -> tuple[list, int]:
    count = struct.unpack_from('<H', data, offset)[0]
    offset += 2
    consts = []
    for _ in range(count):
        tag = data[offset]; offset += 1
        if tag == TAG_NONE: consts.append(None)
        elif tag == TAG_ELLIPSIS: consts.append(Ellipsis)
        elif tag == TAG_BOOL: consts.append(bool(data[offset])); offset += 1
        elif tag == TAG_INT:
            length = struct.unpack_from('<H', data, offset)[0]; offset += 2
            val_bytes = data[offset:offset+length]; offset += length
            consts.append(int.from_bytes(val_bytes, 'little', signed=True))
        elif tag == TAG_FLOAT: 
            consts.append(struct.unpack_from('<d', data, offset)[0]); offset += 8
        elif tag == TAG_COMPLEX: 
            r, i = struct.unpack_from('<dd', data, offset); offset += 16
            consts.append(complex(r, i))
        elif tag == TAG_STRING_REF: 
            idx = struct.unpack_from('<H', data, offset)[0]; offset += 2
            consts.append(pool.strings[idx])
        elif tag == TAG_BYTES:
            length = struct.unpack_from('<I', data, offset)[0]; offset += 4
            consts.append(data[offset:offset+length]); offset += length
        elif tag == TAG_TUPLE:
            items, offset = deserialize_consts(data, offset, end, pool)
            consts.append(tuple(items))
        elif tag == TAG_FROZENSET:
            items, offset = deserialize_consts(data, offset, end, pool)
            consts.append(frozenset(items))
        elif tag == TAG_CODE_REF:
            length = struct.unpack_from('<I', data, offset)[0]; offset += 4
            co, offset = deserialize_code_obj(data, offset, pool)
            consts.append(co)
    return consts, offset