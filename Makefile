# Makefile for managing the nest.service (NestSight) systemd unit

SERVICE := nest.service

.DEFAULT_GOAL := help

.PHONY: help enable enable-now disable start stop restart status logs overlay-on overlay-off overlay-status voltage throttled

help: ## Show all available commands
	@echo "Usage: make <target>"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

enable: ## Enable service to run at boot
	sudo systemctl enable $(SERVICE)

enable-now: ## Enable at boot and start immediately
	sudo systemctl enable --now $(SERVICE)

disable: ## Stop launching at boot
	sudo systemctl disable $(SERVICE)

start: ## Start the service now
	sudo systemctl start $(SERVICE)

stop: ## Stop the service (SIGTERM, waits up to 20s)
	sudo systemctl stop $(SERVICE)

restart: ## Restart the service
	sudo systemctl restart $(SERVICE)

status: ## Show service status
	-systemctl status $(SERVICE) --no-pager

logs: ## Follow live service logs (Ctrl+C to exit)
	journalctl -u $(SERVICE) -f

overlay-on: ## Enable read-only overlay FS (reboot required to take effect)
	sudo raspi-config nonint enable_overlayfs
	@echo "Overlay ENABLED - reboot to take effect. Edits after reboot will NOT persist!"

overlay-off: ## Disable overlay FS to allow persistent edits (reboot required)
	sudo raspi-config nonint disable_overlayfs
	@echo "Overlay DISABLED - reboot to take effect, then edits will persist."

overlay-status: ## Show whether the overlay FS is currently active
	@grep -q overlay /proc/cmdline && echo "overlay ON (read-only, edits will NOT persist)" || echo "overlay OFF (writable)"

voltage: ## Watch the 5V rail voltage every 0.5s (Ctrl+C to exit)
	@watch -n 0.5 vcgencmd pmic_read_adc EXT5V_V

throttled: ## Check under/overvoltage + throttle flags (0x0 = all good)
	@vcgencmd get_throttled
