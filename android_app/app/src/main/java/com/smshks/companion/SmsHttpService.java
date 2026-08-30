package com.smshks.companion;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.IBinder;
import android.telephony.SmsManager;

import org.json.JSONObject;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class SmsHttpService extends Service {
    private static final String CHANNEL_ID = "smshks_phone_service";
    private static final int NOTIFICATION_ID = 8100;
    private static final int PORT = 8000;

    private final ExecutorService executor = Executors.newCachedThreadPool();
    private volatile boolean running = false;
    private ServerSocket serverSocket;

    @Override
    public void onCreate() {
        super.onCreate();
        createNotificationChannel();
        startForeground(NOTIFICATION_ID, buildNotification());
        startServer();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (!running) {
            startServer();
        }
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        running = false;
        try {
            if (serverSocket != null) {
                serverSocket.close();
            }
        } catch (IOException ignored) {
        }
        executor.shutdownNow();
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    private void startServer() {
        if (running) {
            return;
        }
        running = true;
        executor.execute(() -> {
            try {
                serverSocket = new ServerSocket(PORT);
                while (running) {
                    Socket socket = serverSocket.accept();
                    executor.execute(() -> handleClient(socket));
                }
            } catch (IOException ignored) {
                running = false;
            }
        });
    }

    private void handleClient(Socket socket) {
        try (Socket client = socket;
             BufferedInputStream input = new BufferedInputStream(client.getInputStream());
             BufferedOutputStream output = new BufferedOutputStream(client.getOutputStream())) {

            HttpRequest request = readRequest(input);
            if (request == null) {
                writeJson(output, 400, json(false, "طلب غير صالح"));
                return;
            }

            if ("GET".equals(request.method) && "/health".equals(request.path)) {
                JSONObject response = new JSONObject();
                response.put("status", canSendSms() ? "connected" : "permission_required");
                response.put("app", "SmsHks Phone");
                response.put("version", "1.0.0");
                response.put("port", PORT);
                writeJson(output, 200, response.toString());
                return;
            }

            if ("POST".equals(request.method) && "/send".equals(request.path)) {
                if (!canSendSms()) {
                    writeJson(output, 403, json(false, "صلاحية إرسال SMS غير ممنوحة"));
                    return;
                }

                JSONObject body = new JSONObject(request.body == null ? "{}" : request.body);
                String phone = body.optString("phone", "").trim();
                String text = body.optString("text", "").trim();

                if (!phone.matches("^\\+?[0-9]{3,20}$")) {
                    writeJson(output, 400, json(false, "رقم الهاتف غير صالح"));
                    return;
                }
                if (text.isEmpty()) {
                    writeJson(output, 400, json(false, "نص الرسالة فارغ"));
                    return;
                }

                try {
                    sendSms(phone, text);
                    JSONObject response = new JSONObject();
                    response.put("success", true);
                    response.put("message_id", "android-queued");
                    response.put("error", "");
                    writeJson(output, 200, response.toString());
                } catch (Exception ex) {
                    writeJson(output, 500, json(false, ex.getMessage() == null ? "فشل الإرسال" : ex.getMessage()));
                }
                return;
            }

            writeJson(output, 404, json(false, "المسار غير موجود"));
        } catch (Exception ignored) {
        }
    }

    private boolean canSendSms() {
        return checkSelfPermission(Manifest.permission.SEND_SMS) == PackageManager.PERMISSION_GRANTED;
    }

    private void sendSms(String phone, String text) {
        SmsManager manager = SmsManager.getDefault();
        ArrayList<String> parts = manager.divideMessage(text);
        if (parts.size() > 1) {
            manager.sendMultipartTextMessage(phone, null, parts, null, null);
        } else {
            manager.sendTextMessage(phone, null, text, null, null);
        }
    }

    private static class HttpRequest {
        String method;
        String path;
        String body;
    }

    private HttpRequest readRequest(BufferedInputStream input) throws IOException {
        ByteArrayOutputStream headerBytes = new ByteArrayOutputStream();
        int previous3 = -1, previous2 = -1, previous1 = -1;
        int current;
        while ((current = input.read()) != -1) {
            headerBytes.write(current);
            if (previous3 == '\r' && previous2 == '\n' && previous1 == '\r' && current == '\n') {
                break;
            }
            previous3 = previous2;
            previous2 = previous1;
            previous1 = current;
            if (headerBytes.size() > 32 * 1024) {
                return null;
            }
        }

        String headers = headerBytes.toString(StandardCharsets.UTF_8);
        String[] lines = headers.split("\\r\\n");
        if (lines.length == 0) {
            return null;
        }

        String[] requestLine = lines[0].split(" ");
        if (requestLine.length < 2) {
            return null;
        }

        int contentLength = 0;
        for (String line : lines) {
            String lower = line.toLowerCase(Locale.ROOT);
            if (lower.startsWith("content-length:")) {
                try {
                    contentLength = Integer.parseInt(line.substring(line.indexOf(':') + 1).trim());
                } catch (NumberFormatException ignored) {
                    return null;
                }
            }
        }

        if (contentLength < 0 || contentLength > 1024 * 1024) {
            return null;
        }

        byte[] bodyBytes = new byte[contentLength];
        int offset = 0;
        while (offset < contentLength) {
            int read = input.read(bodyBytes, offset, contentLength - offset);
            if (read < 0) {
                break;
            }
            offset += read;
        }

        HttpRequest request = new HttpRequest();
        request.method = requestLine[0].toUpperCase(Locale.ROOT);
        request.path = requestLine[1].split("\\?", 2)[0];
        request.body = new String(bodyBytes, 0, offset, StandardCharsets.UTF_8);
        return request;
    }

    private void writeJson(BufferedOutputStream output, int statusCode, String json) throws IOException {
        byte[] payload = json.getBytes(StandardCharsets.UTF_8);
        String reason = statusCode >= 200 && statusCode < 300 ? "OK" : "Error";
        String headers = "HTTP/1.1 " + statusCode + " " + reason + "\r\n"
                + "Content-Type: application/json; charset=utf-8\r\n"
                + "Content-Length: " + payload.length + "\r\n"
                + "Connection: close\r\n\r\n";
        output.write(headers.getBytes(StandardCharsets.UTF_8));
        output.write(payload);
        output.flush();
    }

    private String json(boolean success, String error) {
        JSONObject response = new JSONObject();
        response.put("success", success);
        response.put("message_id", "");
        response.put("error", error == null ? "" : error);
        return response.toString();
    }

    private void createNotificationChannel() {
        NotificationManager manager = getSystemService(NotificationManager.class);
        NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID,
                "SmsHks Phone Service",
                NotificationManager.IMPORTANCE_LOW);
        manager.createNotificationChannel(channel);
    }

    private Notification buildNotification() {
        Intent openApp = new Intent(this, MainActivity.class);
        PendingIntent pendingIntent = PendingIntent.getActivity(
                this,
                0,
                openApp,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        return new Notification.Builder(this, CHANNEL_ID)
                .setContentTitle("SmsHks Phone")
                .setContentText("جاهز لاستقبال الرسائل من الكمبيوتر")
                .setSmallIcon(android.R.drawable.stat_notify_chat)
                .setContentIntent(pendingIntent)
                .setOngoing(true)
                .build();
    }
}
