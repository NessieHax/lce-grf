

def decompress(buffer: bytes) -> bytes:
    decompressed_buf: bytearray = bytearray()
    pos: int = 0
    while (pos != len(buffer)):
        while True:
            if buffer[pos] == 0xff:
                pos += 1
                break
            decompressed_buf.append(buffer[pos])
            pos += 1
            if pos >= len(buffer):
                return decompressed_buf

        if pos >= len(buffer):
            return decompressed_buf
        count = buffer[pos]
        if count > 2 and (count>>31)&1 == 0:
            pos += 1
            if pos >= len(buffer):
                return decompressed_buf
            val = buffer[pos]
            pos += 1
            for _ in range(count+1):
                decompressed_buf.append(val) 
        else:
            decompressed_buf.append(count)
            pos += 1

        
    return decompressed_buf