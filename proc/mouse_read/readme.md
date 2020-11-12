```
snel@snel-Latitude-7400:~$ ls  -altrh /dev/input/by-id/usb-Razer_Razer_Viper-*
lrwxrwxrwx 1 root root  9 Oct  9 12:16 /dev/input/by-id/usb-Razer_Razer_Viper-mouse -> ../mouse3
lrwxrwxrwx 1 root root 10 Oct  9 12:16 /dev/input/by-id/usb-Razer_Razer_Viper-if01-event-kbd -> ../event20
lrwxrwxrwx 1 root root 10 Oct  9 12:16 /dev/input/by-id/usb-Razer_Razer_Viper-event-if01 -> ../event22
lrwxrwxrwx 1 root root 10 Oct  9 12:16 /dev/input/by-id/usb-Razer_Razer_Viper-if02-event-kbd -> ../event24
lrwxrwxrwx 1 root root 10 Oct  9 12:16 /dev/input/by-id/usb-Razer_Razer_Viper-event-mouse -> ../event19
```

Writing data:
```
XADD mouse_data * dx 0 dy 0 dw 0
```

Reading data:
```
XREAD BLOCK 100000 STREAMS mouseData $
```