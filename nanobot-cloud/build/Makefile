ROOTFS_IMAGE  ?= nanobot-rootfs
ROOTFS_EXT4   ?= /opt/fc-images/nanobot-rootfs.ext4
ROOTFS_SIZE   ?= 512M
KERNEL_URL    ?= https://s3.amazonaws.com/spec.ccfc.min/firecracker-ci/v1.9/x86_64/vmlinux-5.10.225
KERNEL_DEST   ?= /opt/fc-kernels/vmlinux
FC_VERSION    ?= v1.9.0
FC_ARCH       ?= x86_64

.PHONY: all rootfs kernel firecracker dirs clean

all: dirs kernel rootfs

dirs:
	mkdir -p /opt/fc-images /opt/fc-kernels /opt/fc-snapshots /tmp/fc-api /tmp/fc-vsock

## Download Firecracker kernel
kernel:
	@if [ ! -f "$(KERNEL_DEST)" ]; then \
		echo "Downloading kernel..."; \
		curl -fsSL "$(KERNEL_URL)" -o "$(KERNEL_DEST)"; \
	else \
		echo "Kernel already present at $(KERNEL_DEST)"; \
	fi

## Download Firecracker binary
firecracker:
	@if [ ! -f "/usr/bin/firecracker" ]; then \
		curl -fsSL \
		  "https://github.com/firecracker-microvm/firecracker/releases/download/$(FC_VERSION)/firecracker-$(FC_VERSION)-$(FC_ARCH).tgz" \
		  | tar xz --strip-components=1 -C /usr/bin/ \
		  release-$(FC_VERSION)-$(FC_ARCH)/firecracker-$(FC_VERSION)-$(FC_ARCH) && \
		mv /usr/bin/firecracker-$(FC_VERSION)-$(FC_ARCH) /usr/bin/firecracker && \
		chmod +x /usr/bin/firecracker; \
	fi

## Build the ext4 rootfs from the Dockerfile
rootfs:
	@echo "Building rootfs image..."
	docker build \
		-f rootfs.Dockerfile \
		--target rootfs-builder \
		-t "$(ROOTFS_IMAGE)" \
		..
	@echo "Extracting rootfs to ext4..."
	$(eval TMP := $(shell mktemp -d))
	docker create --name rootfs-tmp "$(ROOTFS_IMAGE)"
	docker export rootfs-tmp | tar x -C "$(TMP)"
	docker rm rootfs-tmp
	dd if=/dev/zero of="$(ROOTFS_EXT4)" bs=1M count=512
	mkfs.ext4 "$(ROOTFS_EXT4)"
	$(eval MNT := $(shell mktemp -d))
	mount -o loop "$(ROOTFS_EXT4)" "$(MNT)"
	cp -a "$(TMP)/." "$(MNT)/"
	umount "$(MNT)"
	rm -rf "$(TMP)" "$(MNT)"
	@echo "Rootfs built: $(ROOTFS_EXT4)"

## Create a base snapshot (optional, for fast cold starts)
snapshot:
	@echo "Creating base snapshot..."
	python3 scripts/create_snapshot.py

clean:
	rm -f "$(ROOTFS_EXT4)"
