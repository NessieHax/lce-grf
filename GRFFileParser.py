from dataclasses import dataclass, field
from io import BufferedIOBase, BytesIO
import json
from pprint import pformat
from typing import Optional, OrderedDict
import zlib, struct
import rle

def inflate(data: bytes, buf_size: int):
    decompressor = zlib.decompressobj(-14)
    data = b'\x08\x99' + data
    return decompressor.decompress(data) + decompressor.flush(buf_size)
    return zlib.decompress(data, 0, buf_size)

GRFDetails = OrderedDict[str, str]

@dataclass(slots=True)
class GRFTag:
    name: str
    parent: Optional['GRFTag']
    details: GRFDetails = field(default_factory=GRFDetails, init=False)
    tags: list['GRFTag'] = field(default_factory=list, init=False)

@dataclass(slots=True)
class GRFFileParser:

    GRFRootTag: GRFTag = field(init=False)
    AvaliableTagNames: list[str] = field(default_factory=list)
    Files: list[tuple[str, bytes]] = field(default_factory=list)
    compression: int = field(default=0)

    def parse(self, stream: BufferedIOBase) -> None:
        stream = self.readHeader(stream)
        self.parseTagNames(stream)
        self.parseFileEntries(stream)
        self.parseGRFTags(stream)

    def readHeader(self, stream: BufferedIOBase) -> BufferedIOBase:
        x = self.readShort(stream)
        print(x)
        if (x >> 31 | x) == 0:
            stream.read(14)
            return stream
        self.compression, crc, platform_compression = struct.unpack(">b2i", stream.read(9))
        print(f"{self.compression=} {crc=} {platform_compression=}")

        if self.compression > 0:
            uncompressed_size, compressed_size = self.readInts(stream, 2)
            compressed_data = stream.read(compressed_size)
            data = zlib.decompress(compressed_data, 0, uncompressed_size)
            stream = BytesIO(data)
        if self.compression > 1: # zlib + rle compressed
            data = rle.decompress(stream.read())
            stream = BytesIO(data)

        if self.compression == 0 and crc == 0 and platform_compression == 3:
            size = self.readInt(stream)
            stream = BytesIO(stream.read(size))
            buf_size = self.readInt(stream)
            buf_data = stream.read()
            data = zlib.decompress(buf_data, 0, buf_size) #if platform_compression == 3 else inflate(buf_data, buf_size)
            stream = BytesIO(data)
            data = rle.decompress(stream.read())
            stream = BytesIO(data)
            
            with open("dump.raw.grf", "wb") as f:
                o = stream.tell()
                f.write(stream.read())
                stream.seek(o, 0)

            self.readInt(stream) #! idk
            stream.read(19) #! skip some bytes
            return stream

        return stream

    def parseFileEntries(self, stream: BufferedIOBase) -> None:
        count = self.readInt(stream)
        print(f"schematic file count: {count}")
        for _ in range(count):
            filename = self.readString(stream)
            filesize = self.readInt(stream)
            print(f"{filename=} {filesize=}")
            schematicStream = BytesIO(stream.read(filesize))
            data = self.readSchematicFile(schematicStream)
            with open(f"{filename}.data", "wb") as out:
                out.write(data)

    def parseGRFTags(self, stream: BufferedIOBase) -> None:
        self.GRFRootTag = GRFTag("__ROOT__", None)
        self.GRFRootTag.tags = self.readItemList(stream, self.GRFRootTag)

    def readItemList(self, stream: BufferedIOBase, parent: GRFTag, indent: int = 0) -> list[GRFTag]:
        tags = list()
        count = self.readInt(stream)
        for _ in range(count):
            name, keyValueCount = self.getTagNameAndDetailCount(stream)
            tag = GRFTag(name, parent)
            tag.details = OrderedDict([self.readKeyValuePair(stream) for _ in range(keyValueCount)])
            print(f"{'-'*indent}> {name}: {pformat(tag.details)}")
            tag.tags = self.readItemList(stream, tag, indent+1)
            tags.append(tag)
        return tags

    def getTagNameAndDetailCount(self, stream: BufferedIOBase) -> tuple[str, int]:
        return (self.getTagName(stream), self.readInt(stream))
    
    def readShort(self, stream: BufferedIOBase) -> int:
        return struct.unpack(">h", stream.read(2))[0]

    def readString(self, stream: BufferedIOBase) -> str:
        return stream.read(self.readShort(stream)).decode("UTF-8")

    def readInts(self, stream: BufferedIOBase, count: int) -> tuple[int, ...]:
        return struct.unpack(f">{count}i", stream.read(count*4))

    def readInt(self, stream: BufferedIOBase) -> int:
        return self.readInts(stream, 1)[0]

    def readKeyValuePair(self, stream: BufferedIOBase) -> tuple[str, str]:
        return (self.getTagName(stream), self.readString(stream))

    def parseTagNames(self, stream: BufferedIOBase) -> None:
        self.AvaliableTagNames = [self.readString(stream) for _ in range(self.readInt(stream))]

    def getTagName(self, stream: BufferedIOBase) -> str:
        i = self.readInt(stream)
        return self.AvaliableTagNames[i]
    
    def readSchematicFile(self, stream:BufferedIOBase) -> bytes:
        version = self.readInt(stream)
        # print(f"{version=}")
        compression = 2
        if version > 1: 
            compression = stream.read(1)[0]
            # print(f"{compression=}")

        width, height, length = self.readInts(stream, 3)
        print("Size:", width, height, length)
        
        compressed_data_size = self.readInt(stream)
        
        compressed_data = stream.read(compressed_data_size)

        def calcBlockIdsSizeLegacy(x: int, y: int, z: int) -> int:
            return x * y * z

        def calculateFullElementSize(x: int, y: int, z: int) -> int:
            return x * y * z

        def calcHalfByteDataSizeLegacy(x: int, y: int, z: int) -> int:
            y1 = y + 1
            half_y1 = (y1 // 2)
            yq2 = int(y1 < 0 and (y1 & 1) != 0)
            return x * (half_y1 + yq2) * z
        
        def calcFullDataSizeLegacy(x: int, y: int, z: int) -> int:
            a = calcBlockIdsSizeLegacy(x, y, z)
            b = calcHalfByteDataSizeLegacy(x, y, z)
            return a + b
        
        if version < 3:
            data_size = calcFullDataSizeLegacy(width, height, length)
            # print(f"{data_size=:x}")
            # print(f"{calcBlockIdsSizeLegacy(width, height, length)=:x}")
            if compression == 0:
                compressed_data_size = calculateFullElementSize(width, height, length)
            else:
                if compression == 1:
                    return rle.decompress(compressed_data)
                elif compression == 3:
                    decompressor = zlib.decompressobj(0)
                    try:
                        decompressed_data = decompressor.decompress(compressed_data, compressed_data_size)
                    except Exception as e:
                        print(f"{compression=:x}")
                        print(f"{compressed_data_size=:x}")
                        return bytes()

                    # data = decompressed_data
                    data = rle.decompress(decompressed_data)
                    return data
                
        return bytes()

        
        
    
    def dumpFiles(self) -> None:
        for filename, data in self.Files:
            with open(f"schematic/{filename}", "wb") as file:
                file.write(data) 

    @staticmethod
    def _serialize(tag: GRFTag) -> dict[str, GRFDetails]:
        # tag.details["__Tags__"] = tag.tags
        return {tag.name: tag.details}

    def toJson(self, name: str) -> None:
        if not name.endswith(".json"):
            name += ".json"
        with open(name, "w", encoding="UTF-8") as grfJson:
            json.dump(self.GRFRootTag, grfJson, indent = 4, default = self._serialize)