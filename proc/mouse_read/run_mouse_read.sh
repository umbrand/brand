# ID=$(xinput list --id-only "USB Optical Mouse")
# ## disable the mouse as a user input
# echo "sudo xinput set-prop $ID \"Device Enabled\" 0"
# sudo xinput set-prop $ID "Device Enabled" 0

sudo nice -n -20 ./usbMouse.out /dev/input/by-id/usb-Razer_Razer_Viper-event-mouse 1
