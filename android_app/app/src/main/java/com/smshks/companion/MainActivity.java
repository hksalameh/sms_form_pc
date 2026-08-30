package com.smshks.companion;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.provider.Settings;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

public class MainActivity extends Activity {
    private static final int SMS_PERMISSION_REQUEST = 1001;
    private TextView statusView;
    private String startupError = "";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        boolean backgroundStart = getIntent() != null
                && getIntent().getBooleanExtra("smshks_background", false);

        if (backgroundStart
                && checkSelfPermission(Manifest.permission.SEND_SMS) == PackageManager.PERMISSION_GRANTED) {
            if (startServiceSilently()) {
                finishAndRemoveTask();
                return;
            }
        }

        buildUi();

        if (!startupError.isEmpty()) {
            statusView.setText("تعذر تشغيل خدمة SmsHks\n" + startupError);
            Toast.makeText(this, "فشل تشغيل الخدمة: " + startupError, Toast.LENGTH_LONG).show();
            return;
        }

        ensureSmsPermissionAndStart();
    }

    private void buildUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(48, 48, 48, 48);
        root.setGravity(Gravity.CENTER_HORIZONTAL);

        TextView title = new TextView(this);
        title.setText("SmsHks Phone");
        title.setTextSize(26);
        title.setGravity(Gravity.CENTER);
        root.addView(title, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT));

        TextView description = new TextView(this);
        description.setText("هذا التطبيق يربط الهاتف ببرنامج SmsHks على الكمبيوتر ويرسل الرسائل من شريحة الهاتف.");
        description.setTextSize(16);
        description.setPadding(0, 36, 0, 36);
        description.setGravity(Gravity.CENTER);
        root.addView(description);

        statusView = new TextView(this);
        statusView.setTextSize(18);
        statusView.setGravity(Gravity.CENTER);
        root.addView(statusView, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT));

        Button startButton = new Button(this);
        startButton.setText("تشغيل خدمة SmsHks");
        startButton.setOnClickListener(v -> ensureSmsPermissionAndStart());
        root.addView(startButton, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT));

        Button settingsButton = new Button(this);
        settingsButton.setText("فتح إعدادات التطبيق");
        settingsButton.setOnClickListener(v -> {
            Intent intent = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS);
            intent.setData(android.net.Uri.parse("package:" + getPackageName()));
            startActivity(intent);
        });
        root.addView(settingsButton, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT));

        setContentView(root);
    }

    private void ensureSmsPermissionAndStart() {
        if (checkSelfPermission(Manifest.permission.SEND_SMS) != PackageManager.PERMISSION_GRANTED) {
            statusView.setText("يجب السماح بصلاحية إرسال SMS");
            Toast.makeText(this, "اسمح بصلاحية إرسال الرسائل حتى يعمل SmsHks", Toast.LENGTH_LONG).show();
            requestPermissions(new String[]{Manifest.permission.SEND_SMS}, SMS_PERMISSION_REQUEST);
            return;
        }
        startSmsServiceFromUi();
    }

    private boolean startServiceSilently() {
        try {
            Intent serviceIntent = new Intent(this, SmsHttpService.class);
            startForegroundService(serviceIntent);
            return true;
        } catch (Exception ex) {
            String detail = ex.getMessage();
            if (detail == null || detail.trim().isEmpty()) {
                detail = ex.getClass().getSimpleName();
            }
            startupError = detail;
            return false;
        }
    }

    private void startSmsServiceFromUi() {
        statusView.setText("جاري تشغيل خدمة SmsHks...");
        startupError = "";
        if (startServiceSilently()) {
            statusView.setText("الخدمة تعمل على المنفذ 8000\nيمكنك العودة إلى SmsHks على الكمبيوتر");
            Toast.makeText(this, "تم تشغيل خدمة SmsHks", Toast.LENGTH_SHORT).show();
        } else {
            statusView.setText("تعذر تشغيل خدمة SmsHks\n" + startupError);
            Toast.makeText(this, "فشل تشغيل الخدمة: " + startupError, Toast.LENGTH_LONG).show();
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == SMS_PERMISSION_REQUEST
                && grantResults.length > 0
                && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
            Toast.makeText(this, "تم منح صلاحية SMS", Toast.LENGTH_SHORT).show();
            startSmsServiceFromUi();
        } else if (requestCode == SMS_PERMISSION_REQUEST) {
            statusView.setText("لم يتم منح صلاحية SMS. لن يستطيع البرنامج إرسال الرسائل.");
            Toast.makeText(this, "بدون صلاحية SMS لا يمكن إرسال الرسائل", Toast.LENGTH_LONG).show();
        }
    }
}
