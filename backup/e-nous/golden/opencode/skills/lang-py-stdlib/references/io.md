# io — filesystem access and binary IO

The stdlib disk and byte surface. Sync primitives here; async/throughput file streaming is `para-py-iteration` (aiofile, io_uring/libaio).

## Filesystem — `pathlib` and `os`

- **`pathlib.Path`** for every path: `/` join, `.read_text/bytes`, `.write_text/bytes`, `.glob`, `.stat`, `.exists`. Never string concatenation, never `os.path.join`.
- **`os`** for the operations `pathlib` does not wrap: `os.replace` (atomic rename), `os.scandir` (fast directory iteration with cached `stat`), `os.fspath`, permissions.
- **`tempfile`** — `mkstemp`/`TemporaryDirectory` for scratch that cleans itself; never write next to the target and hope.
- **`shutil`** — whole-tree copy/move/rmtree, `disk_usage`.
- **`glob`/`fnmatch`** — pattern matching when `Path.glob` is not enough; `os.scandir` when you need `stat` while walking.

## Atomic and durable writes

A write that a crash can interrupt must never corrupt the target:

```python
fd, tmp = tempfile.mkstemp(dir=path.parent)   # same filesystem → rename is atomic
with os.fdopen(fd, "wb") as f:
    f.write(data)
    f.flush(); os.fsync(f.fileno())           # durability, when it must survive power loss
os.replace(tmp, path)                         # atomic: readers see old or new, never half
```

Write to a temp file on the **same filesystem**, then `os.replace` — a cross-device rename is not atomic.

## File locking

`fcntl.flock` (POSIX) for advisory locks across processes; a lock file via `O_EXCL` for portability. For coordination beyond one host, that is a distributed concern → `sys-gen-scaling`.

## Binary and buffered

- **`io`** — `BufferedReader`/`BufferedWriter` wrap raw IO; `BytesIO`/`StringIO` are in-memory files for tests and pipes. Read in blocks, not byte by byte.
- **`struct`** — pack/unpack C-layout binary (`struct.unpack("<IHH", buf)`); the format string is the record definition.
- **`mmap`** — map a large file into memory and slice it like `bytes` with no copy and OS-paged loading; the right tool to read gigabytes without holding them.
- **`memoryview`** — a zero-copy window over `bytes`/`bytearray`/`mmap`; slice and pass sub-buffers without duplicating. Pair with `bytearray` for in-place mutation.

Read the bytes with these; parse the *structure* (JSON/config) with a backend, never by hand.
