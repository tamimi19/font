package com.example.font;

import android.os.Bundle;
import android.os.Environment;
import android.Manifest;
import android.content.pm.PackageManager;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;
import android.provider.Settings;
import android.content.Intent;
import android.net.Uri;
import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;
import com.chaquo.python.PyObject;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

public class MainActivity extends AppCompatActivity {

    private static final int PERMISSION_REQUEST_CODE = 100;
    private static final int MANAGE_EXTERNAL_STORAGE_REQUEST_CODE = 101;
    
    private TextView logTextView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        
        // Initialize Python
        if (!Python.isStarted()) {
            Python.start(new AndroidPlatform(this));
        }

        logTextView = findViewById(R.id.log_text_view);
        Button mergeButton = findViewById(R.id.merge_button);
        
        log("تم تشغيل التطبيق. جارٍ التحقق من الصلاحيات...");
        
        mergeButton.setOnClickListener(v -> {
            if (checkPermissions()) {
                startPythonScript();
            } else {
                requestPermissions();
            }
        });
        
        checkPermissions();
    }
    
    private boolean checkPermissions() {
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.R) {
            return Environment.isExternalStorageManager();
        } else {
            int writePermission = ActivityCompat.checkSelfPermission(this, Manifest.permission.WRITE_EXTERNAL_STORAGE);
            int readPermission = ActivityCompat.checkSelfPermission(this, Manifest.permission.READ_EXTERNAL_STORAGE);
            return writePermission == PackageManager.PERMISSION_GRANTED && readPermission == PackageManager.PERMISSION_GRANTED;
        }
    }

    private void requestPermissions() {
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.R) {
            try {
                Intent intent = new Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION);
                intent.addCategory("android.intent.category.DEFAULT");
                intent.setData(Uri.parse(String.format("package:%s", getApplicationContext().getPackageName())));
                startActivityForResult(intent, MANAGE_EXTERNAL_STORAGE_REQUEST_CODE);
                log("يرجى منح صلاحية الوصول الكامل إلى الملفات...");
            } catch (Exception e) {
                Intent intent = new Intent();
                intent.setAction(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION);
                startActivityForResult(intent, MANAGE_EXTERNAL_STORAGE_REQUEST_CODE);
                log("يرجى منح صلاحية الوصول الكامل إلى الملفات...");
            }
        } else {
            ActivityCompat.requestPermissions(
                    this,
                    new String[]{Manifest.permission.READ_EXTERNAL_STORAGE, Manifest.permission.WRITE_EXTERNAL_STORAGE},
                    PERMISSION_REQUEST_CODE
            );
            log("جارٍ طلب صلاحيات التخزين...");
        }
    }
    
    @Override
    public void onRequestPermissionsResult(int requestCode, @NonNull String[] permissions, @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == PERMISSION_REQUEST_CODE) {
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                log("تم منح الصلاحيات. يمكنك الآن بدء الدمج.");
                // Optionally start the script here if the button is not needed
            } else {
                log("تم رفض الصلاحيات. لا يمكن للتطبيق الوصول إلى الملفات.");
                Toast.makeText(this, "Permissions are required to run the script.", Toast.LENGTH_LONG).show();
            }
        }
    }
    
    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == MANAGE_EXTERNAL_STORAGE_REQUEST_CODE) {
            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.R) {
                if (Environment.isExternalStorageManager()) {
                    log("تم منح صلاحية الوصول الكامل إلى الملفات.");
                    // Optionally start the script here
                } else {
                    log("تم رفض صلاحية الوصول الكامل إلى الملفات.");
                    Toast.makeText(this, "All files access permission is required.", Toast.LENGTH_LONG).show();
                }
            }
        }
    }

    private void startPythonScript() {
        log("جارٍ بدء عملية دمج الخطوط...");
        new Thread(() -> {
            try {
                Python py = Python.getInstance();
                PyObject pyModule = py.getModule("font_merger_script");
                
                // Call the main function of the Python script with font names
                // These should be replaced by dynamic user input in a real app
                String arabicFont = "arabic_font_name.ttf";
                String englishFont = "english_font_name.ttf";

                PyObject result = pyModule.callAttr("merge_fonts_android", arabicFont, englishFont);
                final String logOutput = result.toString();
                
                runOnUiThread(() -> {
                    log("اكتملت العملية.");
                    log(logOutput);
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    log("حدث خطأ في سكربت بايثون:\n" + e.getMessage() + "\n" + e.toString());
                });
            }
        }).start();
    }
    
    private void log(String message) {
        runOnUiThread(() -> {
            logTextView.append(message + "\n");
        });
    }
                    }
