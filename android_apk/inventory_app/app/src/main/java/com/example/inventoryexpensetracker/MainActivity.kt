package com.example.inventoryexpensetracker

import android.annotation.SuppressLint
import android.os.Bundle
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.appcompat.app.AppCompatActivity
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File


class MainActivity : AppCompatActivity() {

    private fun copyAssetDir(assetPath: String, targetDir: File) {
        val assets = assets
        val entries = assets.list(assetPath) ?: return
        if (!targetDir.exists()) targetDir.mkdirs()
        for (name in entries) {
            val childAssetPath = if (assetPath.isEmpty()) name else "$assetPath/$name"
            val childTarget = File(targetDir, name)
            val grandChildren = assets.list(childAssetPath)
            if (grandChildren != null && grandChildren.isNotEmpty()) {
                copyAssetDir(childAssetPath, childTarget)
            } else {
                assets.open(childAssetPath).use { input ->
                    childTarget.outputStream().use { output -> input.copyTo(output) }
                }
            }
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Extract web assets (templates/static) into app-private storage.
        val baseDir = File(filesDir, "inventory_app")
        // Always extract during development to ensure code changes are applied.
        baseDir.deleteRecursively()
        copyAssetDir("inventory", baseDir)

        // Initialize Python runtime.
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(this))
        }
        val py = Python.getInstance()

        // Set env vars for Python app paths.
        // Chaquopy exposes os.environ, but we set via Java system properties and read them in Python using os.environ
        // by injecting them in the Python process before importing app.main.
        val dbPath = File(filesDir, "app.db").absolutePath

        val osModule = py.getModule("os")
        val sysModule = py.getModule("sys")
        val path = sysModule.get("path")
        path?.callAttr("insert", 0, baseDir.absolutePath)

        val environ = osModule.get("environ")
        environ?.callAttr("__setitem__", "INVENTORY_BASE_DIR", baseDir.absolutePath)
        environ?.callAttr("__setitem__", "INVENTORY_DB_PATH", dbPath)

        // Start the server.
        py.getModule("app.android_server").callAttr("start_server", "127.0.0.1", 8088)

        // Show the UI.
        setTheme(R.style.Theme_InventoryTracker)
        val webView = WebView(this)
        webView.settings.javaScriptEnabled = true
        
        webView.webViewClient = object : WebViewClient() {
            @Suppress("DEPRECATION")
            override fun onReceivedError(
                view: WebView?,
                errorCode: Int,
                description: String?,
                failingUrl: String?
            ) {
                if (errorCode == ERROR_CONNECT || errorCode == ERROR_TIMEOUT || errorCode == ERROR_HOST_LOOKUP) {
                    view?.postDelayed({ view.loadUrl("http://127.0.0.1:8088/") }, 500)
                }
            }

            override fun onReceivedError(
                view: WebView?,
                request: WebResourceRequest?,
                error: WebResourceError?
            ) {
                if (request?.isForMainFrame == true) {
                    val errorCode = error?.errorCode
                    if (errorCode == ERROR_CONNECT || errorCode == ERROR_TIMEOUT || errorCode == ERROR_HOST_LOOKUP) {
                        view?.postDelayed({ view.loadUrl("http://127.0.0.1:8088/") }, 500)
                    }
                }
            }
        }

        webView.loadUrl("http://127.0.0.1:8088/")
        setContentView(webView)
    }
}

