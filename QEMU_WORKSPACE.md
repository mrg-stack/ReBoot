# ReBoot application workspace

The local application directory is shared live with the ReBoot QEMU
development VM:

```text
~/Developer/ReBoot/app/ -> /mnt/reboot-app/
```

The application entry point is:

```text
~/Developer/ReBoot/app/main.py
```

Inside the Linux desktop, use **Run Shared ReBoot App** for a normal window or
**Test Shared App Fullscreen** for production-style fullscreen behavior.

Changes saved on the Mac are immediately visible inside the running VM. The
local application directory is not embedded in the ISO.
