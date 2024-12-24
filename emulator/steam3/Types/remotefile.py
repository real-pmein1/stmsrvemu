class RemoteFile:
    def __init__(self, app_id, name, sha, time, size):
        self.app_id = app_id
        self.name = name
        self.sha = sha
        self.time = time
        self.size = size

    def __str__(self):
        return (
            f"RemoteFile(app_id={self.app_id}, name={self.name}, "
            f"sha={self.sha.hex()}, time={self.time}, size={self.size})"
        )