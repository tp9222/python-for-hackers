def generate_text_file(filename, size_mb):
    total_bytes = size_mb * 1024 * 1024
    chunk = "A" * 1024  # 1 KB chunk
    written = 0

    with open(filename, 'w') as f:
        while written < total_bytes:
            to_write = chunk if total_bytes - written >= 1024 else "A" * (total_bytes - written)
            f.write(to_write)
            written += len(to_write)

    print(f"Generated '{filename}' with size {size_mb} MB ({total_bytes} bytes)")

# Example usage:
if __name__ == "__main__":
    filename = input("Enter filename (e.g., large.txt): ")
    size_mb = int(input("Enter file size in MB: "))
    generate_text_file(filename, size_mb)
