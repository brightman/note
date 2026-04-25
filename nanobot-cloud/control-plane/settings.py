from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NC_", env_file=".env")

    # Database
    database_url: str = "postgresql+asyncpg://nanobot:nanobot@localhost:5432/nanobot"
    database_url_sync: str = "postgresql://nanobot:nanobot@localhost:5432/nanobot"

    # S3 / MinIO
    s3_endpoint: str = "http://localhost:9000"
    s3_bucket: str = "nanobot-data"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"

    # Auth
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    # Encryption key for MCP env secrets (Fernet 32-byte base64)
    encryption_key: str = "change-me-32-byte-base64-encoded=="

    # Firecracker
    fc_binary: str = "/usr/bin/firecracker"
    fc_kernel: str = "/opt/fc-kernels/vmlinux"
    fc_rootfs: str = "/opt/fc-images/nanobot-rootfs.ext4"
    fc_snapshot_base: str = "/opt/fc-snapshots/nanobot-base"
    fc_api_sock_dir: str = "/tmp/fc-api"
    fc_vsock_dir: str = "/tmp/fc-vsock"
    fc_tap_prefix: str = "tap-nb"

    # VM resource limits
    vm_vcpu: int = 1
    vm_mem_mib: int = 256

    # Idle timeout in seconds
    vm_idle_timeout: int = 1800  # 30 minutes
    vm_reaper_interval: int = 60  # check every 60s

    # Host networking
    host_gateway_ip: str = "172.16.0.1"
    vm_subnet: str = "172.16.0.0/16"


settings = Settings()
