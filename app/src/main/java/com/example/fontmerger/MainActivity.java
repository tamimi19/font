package com.example.font;

import androidx.appcompat.app.AppCompatActivity;
import android.os.Bundle;

public class MainActivity extends AppCompatActivity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        // The previous build error was related to the theme.
        // This class must extend AppCompatActivity to properly use an AppCompat theme.

        // It is assumed your main layout file is named activity_main.xml
        // If your layout file has a different name, please replace 'activity_main' below.
        setContentView(R.layout.activity_main);
    }
}
