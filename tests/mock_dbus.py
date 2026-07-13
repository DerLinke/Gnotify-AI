import sys
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

class NotificationService(dbus.service.Object):
    def __init__(self, bus, path):
        super().__init__(bus, path)
        self.counter = 0

    @dbus.service.method('org.freedesktop.Notifications',
                         in_signature='susssasa{sv}i',
                         out_signature='u')
    def Notify(self, app_name, replaces_id, app_icon, summary, body, actions, hints, expire_timeout):
        try:
            self.counter += 1
            print(f"MockDbusNotify: app_name='{app_name}', summary='{summary}', body='{body}', id={self.counter}", flush=True)
            res = dbus.UInt32(self.counter)
            print(f"Returning from MockDbusNotify: {res}", flush=True)
            return res
        except Exception as e:
            print(f"EXCEPTION in MockDbusNotify: {e}", file=sys.stderr, flush=True)
            raise

    @dbus.service.method('org.freedesktop.Notifications',
                         in_signature='',
                         out_signature='ssss')
    def GetServerInformation(self):
        return ("GnotifyMock", "DerLinke", "1.0", "1.2")

    @dbus.service.method('org.freedesktop.Notifications',
                         in_signature='',
                         out_signature='as')
    def GetCapabilities(self):
        return ["body", "actions"]

def main():
    DBusGMainLoop(set_as_default=True)
    session_bus = dbus.SessionBus()
    try:
        name = dbus.service.BusName('org.freedesktop.Notifications', session_bus)
    except Exception as e:
        print(f"Error registering BusName: {e}", file=sys.stderr)
        sys.exit(1)
        
    service = NotificationService(session_bus, '/org/freedesktop/Notifications')
    
    loop = GLib.MainLoop()
    print("Mock D-Bus Notification Service is running...", flush=True)
    loop.run()

if __name__ == '__main__':
    main()
