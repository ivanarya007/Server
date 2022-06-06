import math, time
from fastapi import Request, APIRouter, status
from fastapi.responses import StreamingResponse


def chunk_size(length):
    return 1024 * 1024
    # return 2 ** max(min(math.ceil(math.log2(length / 1024)), 10), 2) * 1024

router = APIRouter(
    prefix="/stream",
    tags=["internals"],
)

def offset_fix(offset, chunksize):
    offset -= offset % chunksize
    return offset

excluded_headers = [
    "content-encoding",
    "content-length",
    "transfer-encoding",
    "connection",
    "host",
]

@router.get("/{rclone_index}/{full_path:path}")
def query(request: Request, full_path: str, rclone_index: int):
    from main import rclone
    st_time  = time.perf_counter()
    rc = rclone[rclone_index]
    # req_headers = request.headers.items()
    # res_headers = {
    #     "Cache-Control": "no-cache, no-store, must-revalidate",
    #     "Pragma": "no-cache",
    #     "Accept-Ranges": "bytes",
    # }
    # for item in req_headers:
    #     if item[0].lower() not in excluded_headers:
    #         res_headers[item[0]] = item[1]

    range_header = request.headers.get("range")
    file_size = rc.size(full_path)
    print("After size:", time.perf_counter() - st_time)
    content_type = "video/mp4"
    if range_header:
        from_bytes, until_bytes = range_header.replace("bytes=", "").split("-")
        from_bytes = int(from_bytes)
        until_bytes = int(until_bytes) if until_bytes else file_size - 1
    else:
        from_bytes =  0
        until_bytes = file_size - 1
    
    req_length = until_bytes - from_bytes
    new_chunk_size = chunk_size(req_length)
    offset = offset_fix(from_bytes, new_chunk_size)
    first_part_cut = from_bytes - offset
    last_part_cut = (until_bytes % new_chunk_size) + 1
    part_count = math.ceil(req_length / new_chunk_size)
    print(f"{range_header=}")
    
    print("After fetch data:", time.perf_counter() - st_time)
    result = rc.yield_stream(
        full_path,
        chunk_size=new_chunk_size,
        offset=offset,
        total_size=file_size,
        first_part_cut=first_part_cut,
        last_part_cut=last_part_cut,
        part_count=part_count
    )
    return StreamingResponse(result, media_type="video/mp4", headers={
            "Content-Type": content_type,
            "Range": f"bytes={from_bytes}-{until_bytes}",
            "Content-Range": f"bytes {from_bytes}-{until_bytes}/{file_size}",
            "Accept-Ranges": "bytes",
        },
        status_code=status.HTTP_206_PARTIAL_CONTENT if range_header else status.HTTP_200_OK)