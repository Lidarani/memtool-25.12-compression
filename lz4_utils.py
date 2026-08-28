from dataclasses import dataclass
import struct
from typing import Iterator, Tuple

import lz4.block
import lz4.frame

from memtool.utils.constants import Const


DDR_FW_COMPRESSED_MAGIC = 0x44445243
DDR_FW_COMPRESSED_VERSION = 1
DDR_FW_COMPRESSED_CHUNK_SIZE = 1024
DDR_FW_COMPRESSED_HEADER_FORMAT = '<7I'
DDR_FW_COMPRESSED_HEADER_SIZE = struct.calcsize(DDR_FW_COMPRESSED_HEADER_FORMAT)


@dataclass(frozen=True)
class ChunkedDdrFirmware:
    """Encoded DDR firmware and the metadata required by its OEI loader."""

    data: bytes
    imem_compressed_size: int
    dmem_compressed_size: int
    imem_chunk_count: int
    dmem_chunk_count: int


def _compress_chunks(data: bytes, chunk_size: int) -> Tuple[list[bytes], list[int]]:
    chunks = [data[offset:offset + chunk_size] for offset in range(0, len(data), chunk_size)]
    compressed_chunks = [
        lz4.block.compress(chunk, mode='high_compression', compression=Const.LZ4_COMPRESSION_LEVEL,
                           store_size=False)
        for chunk in chunks
    ]
    return compressed_chunks, [len(chunk) for chunk in compressed_chunks]


def build_chunked_ddr_firmware(
        imem_data: bytes, dmem_data: bytes, chunk_size: int = DDR_FW_COMPRESSED_CHUNK_SIZE) -> ChunkedDdrFirmware:
    """Encode IMEM and DMEM as independently decompressible raw LZ4 blocks.

    The payload layout is a seven-word header, compressed-size tables for IMEM and
    DMEM, followed by all IMEM blocks and then all DMEM blocks. The C OEI can
    therefore decode one chunk into a fixed-size buffer before passing it to EDMA.
    """
    if chunk_size <= 0:
        raise ValueError('chunk_size must be positive')

    imem_chunks, imem_sizes = _compress_chunks(imem_data, chunk_size)
    dmem_chunks, dmem_sizes = _compress_chunks(dmem_data, chunk_size)
    header = struct.pack(
        DDR_FW_COMPRESSED_HEADER_FORMAT,
        DDR_FW_COMPRESSED_MAGIC,
        DDR_FW_COMPRESSED_VERSION,
        chunk_size,
        len(imem_data),
        len(dmem_data),
        len(imem_chunks),
        len(dmem_chunks),
    )
    size_table = struct.pack(f'<{len(imem_sizes) + len(dmem_sizes)}I', *(imem_sizes + dmem_sizes))
    return ChunkedDdrFirmware(
        data=header + size_table + b''.join(imem_chunks) + b''.join(dmem_chunks),
        imem_compressed_size=sum(imem_sizes),
        dmem_compressed_size=sum(dmem_sizes),
        imem_chunk_count=len(imem_chunks),
        dmem_chunk_count=len(dmem_chunks),
    )


def iter_chunked_ddr_firmware(data: bytes) -> Iterator[Tuple[str, int, bytes]]:
    """Yield validated decompressed DDR chunks for host-side payload verification."""
    if len(data) < DDR_FW_COMPRESSED_HEADER_SIZE:
        raise ValueError('compressed DDR firmware is missing its header')

    magic, version, chunk_size, imem_size, dmem_size, imem_count, dmem_count = struct.unpack_from(
        DDR_FW_COMPRESSED_HEADER_FORMAT, data)
    if magic != DDR_FW_COMPRESSED_MAGIC or version != DDR_FW_COMPRESSED_VERSION:
        raise ValueError('unsupported compressed DDR firmware format')
    if chunk_size == 0:
        raise ValueError('compressed DDR firmware has an invalid chunk size')

    chunk_count = imem_count + dmem_count
    table_end = DDR_FW_COMPRESSED_HEADER_SIZE + chunk_count * 4
    if len(data) < table_end:
        raise ValueError('compressed DDR firmware is missing its chunk table')
    compressed_sizes = struct.unpack_from(f'<{chunk_count}I', data, DDR_FW_COMPRESSED_HEADER_SIZE)
    payload_offset = table_end

    for stream_name, stream_size, stream_count, table_offset in (
            ('imem', imem_size, imem_count, 0),
            ('dmem', dmem_size, dmem_count, imem_count)):
        output_offset = 0
        for chunk_index in range(stream_count):
            compressed_size = compressed_sizes[table_offset + chunk_index]
            payload_end = payload_offset + compressed_size
            expected_size = min(chunk_size, stream_size - output_offset)
            if expected_size <= 0 or payload_end > len(data):
                raise ValueError('compressed DDR firmware has an invalid chunk payload')
            chunk = lz4.block.decompress(data[payload_offset:payload_end], uncompressed_size=expected_size)
            if len(chunk) != expected_size:
                raise ValueError('compressed DDR firmware chunk has an unexpected size')
            yield stream_name, output_offset, chunk
            output_offset += len(chunk)
            payload_offset = payload_end
        if output_offset != stream_size:
            raise ValueError('compressed DDR firmware stream size does not match its chunk table')

    if payload_offset != len(data):
        raise ValueError('compressed DDR firmware has trailing bytes')


class ChunkedDecompressStream:
    """Stream decompressed bytes in fixed-size chunks without materializing the whole image.

    The implementation keeps the compressed payload intact and yields the decompressed
    output in slices. This matches the "decompress a little, DMA a little, repeat"
    model described for the OEI flow.
    """

    def __init__(self, compressed_data: bytes, chunk_size: int = 1024):
        self._compressed_data = compressed_data
        self._chunk_size = max(1, chunk_size)
        self._decompressed_data = None
        self._offset = 0
        self._finished = False

    def _ensure_decompressed(self) -> bytes:
        if self._decompressed_data is None:
            self._decompressed_data = lz4.frame.decompress(self._compressed_data)
        return self._decompressed_data

    def next_chunk(self):
        """Return the next (offset, chunk) tuple or None when exhausted."""
        if self._finished:
            return None

        data = self._ensure_decompressed()
        if self._offset >= len(data):
            self._finished = True
            return None

        end = min(self._offset + self._chunk_size, len(data))
        chunk = data[self._offset:end]
        self._offset = end
        if self._offset >= len(data):
            self._finished = True
        return self._offset - len(chunk), chunk


def stream_decompressed_chunks(compressed_data: bytes, chunk_size: int = 1024, on_chunk=None):
    """Yield decompressed chunks and optionally invoke a callback for each chunk."""
    stream = ChunkedDecompressStream(compressed_data, chunk_size=chunk_size)
    while True:
        item = stream.next_chunk()
        if item is None:
            break
        offset, chunk = item
        if on_chunk is not None:
            on_chunk(offset, chunk)
        yield offset, chunk


def compress_binary(data: bytes) -> bytes:
    """Compress binary data using LZ4 algorithm.

    @param data: binary data to be compressed
    @return: compressed binary data
    """
    return lz4.frame.compress(data, compression_level=Const.LZ4_COMPRESSION_LEVEL)


def decompress_binary(data: bytes) -> bytes:
    """Decompress binary data using LZ4 algorithm.

    @param data: compressed binary data to be decompressed
    @return: decompressed binary data
    """
    return lz4.frame.decompress(data)

