package com.example.fontmerger;

import androidx.appcompat.app.AppCompatActivity;
import android.os.Bundle;
import android.widget.*;
import android.view.View;
import com.chaquo.python.PyObject;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

public class MainActivity extends AppCompatActivity {
    EditText editArabic, editEnglish;
    Button btnMerge;
    TextView textResult;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        editArabic = findViewById(R.id.editArabic);
        editEnglish = findViewById(R.id.editEnglish);
        btnMerge = findViewById(R.id.btnMerge);
        textResult = findViewById(R.id.textResult);

        if (! Python.isStarted()) {
            Python.start(new AndroidPlatform(this));
        }
        Python py = Python.getInstance();
        PyObject script = py.getModule("font_merger_script");

        btnMerge.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                String arabicFont = editArabic.getText().toString().trim();
                String englishFont = editEnglish.getText().toString().trim();
                if (arabicFont.isEmpty() || englishFont.isEmpty()) {
                    textResult.setText("يرجى إدخال اسم ملفي الخطوط كما هي في مجلد fonts");
                    return;
                }
                try {
                    PyObject result = script.callAttr("merge_fonts_android", arabicFont, englishFont, getFilesDir().getAbsolutePath());
                    textResult.setText(result.toString());
                } catch (Exception e) {
                    textResult.setText("حدث خطأ: " + e.getMessage());
                }
            }
        });
    }
}