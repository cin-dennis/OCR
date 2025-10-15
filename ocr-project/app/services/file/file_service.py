class FileService:
    def __init__(self, bucket_name: str, allow_types: set[str]) -> None:
        self.bucket_name = bucket_name
        self.allow_types = allow_types

    def is_allowed_file_type(self, content_type: str) -> bool:
        return content_type in self.allow_types
