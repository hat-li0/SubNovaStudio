package com.subtitlepro.studio.engine.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import androidx.core.app.NotificationCompat
import com.subtitlepro.studio.MainActivity

class TranslationForegroundService : Service() {

    private var wakeLock: PowerManager.WakeLock? = null
    private lateinit var notificationManager: NotificationManager

    companion object {
        const val CHANNEL_ID = "subnova_translation_channel"
        const val NOTIFICATION_ID = 2026
        const val ACTION_START = "com.subtitlepro.studio.action.START"
        const val ACTION_UPDATE = "com.subtitlepro.studio.action.UPDATE"
        const val ACTION_STOP = "com.subtitlepro.studio.action.STOP"
        const val ACTION_CANCEL = "com.subtitlepro.studio.action.CANCEL"

        const val EXTRA_CURRENT_BATCH = "extra_current_batch"
        const val EXTRA_TOTAL_BATCHES = "extra_total_batches"
        const val EXTRA_PROCESSED_LINES = "extra_processed_lines"
        const val EXTRA_TOTAL_LINES = "extra_total_lines"
        const val EXTRA_MESSAGE = "extra_message"

        var isRunning: Boolean = false
            private set

        var onCancelCallback: (() -> Unit)? = null

        fun startService(
            context: Context,
            currentBatch: Int = 1,
            totalBatches: Int = 1,
            processedLines: Int = 0,
            totalLines: Int = 0,
            message: String = "بدء خط المعالجة والترجمة..."
        ) {
            val intent = Intent(context, TranslationForegroundService::class.java).apply {
                action = ACTION_START
                putExtra(EXTRA_CURRENT_BATCH, currentBatch)
                putExtra(EXTRA_TOTAL_BATCHES, totalBatches)
                putExtra(EXTRA_PROCESSED_LINES, processedLines)
                putExtra(EXTRA_TOTAL_LINES, totalLines)
                putExtra(EXTRA_MESSAGE, message)
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        }

        fun updateProgress(
            context: Context,
            currentBatch: Int,
            totalBatches: Int,
            processedLines: Int,
            totalLines: Int,
            message: String
        ) {
            val intent = Intent(context, TranslationForegroundService::class.java).apply {
                action = ACTION_UPDATE
                putExtra(EXTRA_CURRENT_BATCH, currentBatch)
                putExtra(EXTRA_TOTAL_BATCHES, totalBatches)
                putExtra(EXTRA_PROCESSED_LINES, processedLines)
                putExtra(EXTRA_TOTAL_LINES, totalLines)
                putExtra(EXTRA_MESSAGE, message)
            }
            context.startService(intent)
        }

        fun stopService(context: Context) {
            val intent = Intent(context, TranslationForegroundService::class.java).apply {
                action = ACTION_STOP
            }
            context.startService(intent)
        }
    }

    override fun onCreate() {
        super.onCreate()
        notificationManager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        createNotificationChannel()
        acquireWakeLock()
        isRunning = true
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_CANCEL -> {
                onCancelCallback?.invoke()
                stopForegroundAndService()
                return START_NOT_STICKY
            }
            ACTION_STOP -> {
                stopForegroundAndService()
                return START_NOT_STICKY
            }
            ACTION_UPDATE -> {
                val currentBatch = intent.getIntExtra(EXTRA_CURRENT_BATCH, 1)
                val totalBatches = intent.getIntExtra(EXTRA_TOTAL_BATCHES, 1)
                val processedLines = intent.getIntExtra(EXTRA_PROCESSED_LINES, 0)
                val totalLines = intent.getIntExtra(EXTRA_TOTAL_LINES, 0)
                val msg = intent.getStringExtra(EXTRA_MESSAGE) ?: "جاري الترجمة والتحسين..."
                updateNotification(currentBatch, totalBatches, processedLines, totalLines, msg)
            }
            ACTION_START, null -> {
                val currentBatch = intent?.getIntExtra(EXTRA_CURRENT_BATCH, 1) ?: 1
                val totalBatches = intent?.getIntExtra(EXTRA_TOTAL_BATCHES, 1) ?: 1
                val processedLines = intent?.getIntExtra(EXTRA_PROCESSED_LINES, 0) ?: 0
                val totalLines = intent?.getIntExtra(EXTRA_TOTAL_LINES, 0) ?: 0
                val msg = intent?.getStringExtra(EXTRA_MESSAGE) ?: "جاري تشغيل خط الإنتاج..."
                val notification = buildNotification(currentBatch, totalBatches, processedLines, totalLines, msg)
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                    startForeground(
                        NOTIFICATION_ID,
                        notification,
                        android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC
                    )
                } else {
                    startForeground(NOTIFICATION_ID, notification)
                }
            }
        }
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        releaseWakeLock()
        isRunning = false
        super.onDestroy()
    }

    private fun acquireWakeLock() {
        try {
            if (wakeLock == null) {
                val powerManager = getSystemService(Context.POWER_SERVICE) as PowerManager
                wakeLock = powerManager.newWakeLock(
                    PowerManager.PARTIAL_WAKE_LOCK,
                    "SubNovaStudio:TranslationWakeLock"
                ).apply {
                    setReferenceCounted(false)
                    acquire(12 * 60 * 60 * 1000L) // 12 hours max safety
                }
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    private fun releaseWakeLock() {
        try {
            wakeLock?.let {
                if (it.isHeld) {
                    it.release()
                }
            }
            wakeLock = null
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "خدمة ترجمة SubNova في الخلفية",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "إشعار مستمر يضمن عدم إيقاف خط الترجمة في الخلفية عند قفل الشاشة"
                setShowBadge(false)
            }
            notificationManager.createNotificationChannel(channel)
        }
    }

    private fun buildNotification(
        currentBatch: Int,
        totalBatches: Int,
        processedLines: Int,
        totalLines: Int,
        message: String
    ): Notification {
        val openAppIntent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val contentPendingIntent = PendingIntent.getActivity(
            this,
            0,
            openAppIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or (if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) PendingIntent.FLAG_IMMUTABLE else 0)
        )

        val cancelIntent = Intent(this, TranslationForegroundService::class.java).apply {
            action = ACTION_CANCEL
        }
        val cancelPendingIntent = PendingIntent.getService(
            this,
            1,
            cancelIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or (if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) PendingIntent.FLAG_IMMUTABLE else 0)
        )

        val pct = if (totalBatches > 0) ((currentBatch.toFloat() / totalBatches) * 100).toInt() else 0

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("SubNova Studio — جاري الترجمة ($pct%)")
            .setContentText("الدفعة $currentBatch من $totalBatches | $processedLines من $totalLines سطر")
            .setSubText(message)
            .setSmallIcon(android.R.drawable.stat_notify_sync)
            .setContentIntent(contentPendingIntent)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setProgress(if (totalBatches > 0) totalBatches else 100, currentBatch, totalBatches <= 0)
            .addAction(android.R.drawable.ic_menu_close_clear_cancel, "إلغاء الترجمة", cancelPendingIntent)
            .build()
    }

    private fun updateNotification(
        currentBatch: Int,
        totalBatches: Int,
        processedLines: Int,
        totalLines: Int,
        message: String
    ) {
        val notification = buildNotification(currentBatch, totalBatches, processedLines, totalLines, message)
        notificationManager.notify(NOTIFICATION_ID, notification)
    }

    private fun stopForegroundAndService() {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
                stopForeground(STOP_FOREGROUND_REMOVE)
            } else {
                @Suppress("DEPRECATION")
                stopForeground(true)
            }
        } catch (ignored: Exception) {}
        stopSelf()
    }
}
