# ReBoot application workspace

This directory is shared live with the ReBoot QEMU development VM at:

```text
/mnt/reboot-app
```

The recovered application entry point is:

```text
application/app/main.py
```

Inside the Linux desktop, use **Run Shared ReBoot App** for a normal window or
**Test Shared App Fullscreen** for production-style fullscreen behavior.

Changes saved on the Mac are immediately visible inside the running VM. The
`application/app/` directory is not embedded in the ISO.
