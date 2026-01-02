# alfagold/core/tokenizer.py
import re
from collections import defaultdict, Counter

class AlfagoldTokenizer:
    def __init__(self):
        self.byte_encoder = self.bytes_to_unicode()
        self.byte_decoder = {v: k for k, v in self.byte_encoder.items()}
        
        self.vocab = {}         
        self.inverse_vocab = {} 
        self.bpe_ranks = {}
        self.cache = {}
        self.vocab_size = 0

    def bytes_to_unicode(self):
        bs = list(range(ord("!"), ord("~")+1)) + list(range(ord("¡"), ord("¬")+1)) + list(range(ord("®"), ord("ÿ")+1))
        cs = bs[:]
        n = 0
        for b in range(2**8):
            if b not in bs:
                bs.append(b)
                cs.append(256 + n)
                n += 1
        cs = [chr(n) for n in cs]
        return dict(zip(bs, cs))

    def get_stats(self, vocab):
        pairs = defaultdict(int)
        for word, freq in vocab.items():
            symbols = word.split()
            for i in range(len(symbols)-1):
                pairs[symbols[i], symbols[i+1]] += freq
        return pairs

    def merge_vocab(self, pair, v_in):
        v_out = {}
        bigram = re.escape(' '.join(pair))
        p = re.compile(r'(?<!\S)' + bigram + r'(?!\S)')
        for word in v_in:
            w_out = p.sub(''.join(pair), word)
            v_out[w_out] = v_in[word]
        return v_out

    def train(self, text, vocab_size=1000):
        print(f"   🔨 [BPE] Treinando Tokenizer (Alvo: {vocab_size})...")
        tokens_raw = re.findall(r"\w+|[^\w\s]", text, re.UNICODE)
        
        vocab = Counter()
        for token in tokens_raw:
            chars = " ".join([self.byte_encoder[b] for b in token.encode('utf-8')])
            vocab[chars] += 1

        self.vocab_size = vocab_size
        num_merges = max(0, vocab_size - 300) 
        
        for i in range(num_merges):
            pairs = self.get_stats(vocab)
            if not pairs: break
            best = max(pairs, key=pairs.get)
            self.bpe_ranks[best] = i
            vocab = self.merge_vocab(best, vocab)

        print("   🔨 [BPE] Mapeando IDs Únicos...")
        self.vocab = {}
        self.inverse_vocab = {}
        current_id = 0
        
        for b in self.byte_encoder.values():
            self.vocab[b] = current_id
            self.inverse_vocab[current_id] = b
            current_id += 1
            
        for word in sorted(vocab.keys()):
            token = word.replace(' ', '')
            if token not in self.vocab:
                self.vocab[token] = current_id
                self.inverse_vocab[current_id] = token
                current_id += 1
                
        for special in ["<UNK>", "<PAD>", "ENDMARKER"]:
            if special not in self.vocab:
                self.vocab[special] = current_id
                self.inverse_vocab[current_id] = special
                current_id += 1
        
        print(f"   ✅ [BPE] Concluído. Vocab Final: {len(self.vocab)}")

    def bpe(self, token):
        if token in self.cache: return self.cache[token]
        word = tuple([self.byte_encoder[b] for b in token.encode('utf-8')])
        pairs = self.get_stats({ " ".join(word): 1 })

        if not pairs: return token

        while True:
            bigram = min(pairs, key=lambda pair: self.bpe_ranks.get(pair, float('inf')))
            if bigram not in self.bpe_ranks: break
            first, second = bigram
            new_word = []
            i = 0
            while i < len(word):
                try: j = word.index(first, i)
                except ValueError: 
                    new_word.extend(word[i:])
                    break
                new_word.extend(word[i:j])
                i = j
                if word[i] == first and i < len(word)-1 and word[i+1] == second:
                    new_word.append(first+second)
                    i += 2
                else:
                    new_word.append(word[i])
                    i += 1
            word = tuple(new_word)
            if len(word) == 1: break
            pairs = self.get_stats({ " ".join(word): 1 })

        word = " ".join(word)
        self.cache[token] = word
        return word

    def encode(self, text):
        tokens_raw = re.findall(r"\w+|[^\w\s]", text, re.UNICODE)
        ids = []
        unk_id = self.vocab.get("<UNK>", 0)
        for token in tokens_raw:
            if not token: continue
            bpe_tokens = self.bpe(token).split(' ')
            for t in bpe_tokens:
                token_id = self.vocab.get(t, unk_id)
                ids.append(token_id)
        return ids

    def decode(self, ids):
        text = ""
        for i in ids:
            token = self.inverse_vocab.get(i, "")
            if token in ["<UNK>", "<PAD>", "ENDMARKER"]: continue
            chars = []
            for c in token:
                if c in self.byte_decoder: chars.append(chr(self.byte_decoder[c]))
                else: chars.append(c)
            part = "".join(chars)
            if len(text) > 0 and part.isalnum() and text[-1].isalnum(): text += " " + part
            else: text += part
        return text

    # [FIX] Métodos de Serialização JSON-Friendly
    def get_state(self):
        """Retorna estado serializável em JSON."""
        # Converte chaves de tupla ('a', 'b') para string "a b"
        serialized_ranks = {f"{k[0]} {k[1]}": v for k, v in self.bpe_ranks.items()}
        return {
            'vocab': self.vocab,
            'inverse_vocab': {str(k): v for k, v in self.inverse_vocab.items()}, # Chaves JSON devem ser string
            'bpe_ranks': serialized_ranks,
            'vocab_size': self.vocab_size
        }

    def set_state(self, state):
        """Restaura estado do JSON."""
        self.vocab = state['vocab']
        # Converte chaves de volta para int
        self.inverse_vocab = {int(k): v for k, v in state['inverse_vocab'].items()}
        self.vocab_size = state.get('vocab_size', 0)
        
        # Restaura tuplas dos ranks
        self.bpe_ranks = {}
        for k, v in state['bpe_ranks'].items():
            parts = k.split(" ")
            if len(parts) == 2:
                self.bpe_ranks[tuple(parts)] = v