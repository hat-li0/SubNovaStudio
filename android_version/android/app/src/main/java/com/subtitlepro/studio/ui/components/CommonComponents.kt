package com.subtitlepro.studio.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Chat
import androidx.compose.material.icons.automirrored.filled.List
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Movie
import androidx.compose.material.icons.filled.People
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.subtitlepro.studio.data.model.TranslationStatus
import com.subtitlepro.studio.ui.theme.AmberAccent
import com.subtitlepro.studio.ui.theme.DangerRed
import com.subtitlepro.studio.ui.theme.DarkBorder
import com.subtitlepro.studio.ui.theme.DarkCard
import com.subtitlepro.studio.ui.theme.DarkSurface
import com.subtitlepro.studio.ui.theme.NeonCyan
import com.subtitlepro.studio.ui.theme.NeonGreen
import com.subtitlepro.studio.ui.theme.TextPrimary
import com.subtitlepro.studio.ui.theme.TextSecondary

data class NavTabItem(
    val title: String,
    val icon: ImageVector,
    val index: Int
)

val NAV_TABS = listOf(
    NavTabItem("الاستوديو", Icons.Default.Movie, 0),
    NavTabItem("المعاينة", Icons.AutoMirrored.Filled.List, 1),
    NavTabItem("الشخصيات", Icons.Default.People, 2),
    NavTabItem("المزود", Icons.Default.Settings, 3),
    NavTabItem("السجل", Icons.AutoMirrored.Filled.Chat, 4)
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AppTopBar(status: TranslationStatus) {
    var showAboutDialog by remember { mutableStateOf(false) }

    TopAppBar(
        title = {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.Start
            ) {
                Icon(
                    imageVector = Icons.Default.AutoAwesome,
                    contentDescription = null,
                    tint = AmberAccent,
                    modifier = Modifier.size(20.dp)
                )
                Spacer(modifier = Modifier.width(6.dp))
                Text(
                    text = "SubNova Studio",
                    color = NeonCyan,
                    fontSize = 17.sp,
                    fontWeight = FontWeight.Bold
                )
                Spacer(modifier = Modifier.width(8.dp))
                StatusIndicatorBadge(status = status)
            }
        },
        actions = {
            IconButton(onClick = { showAboutDialog = true }) {
                Icon(
                    imageVector = Icons.Default.Info,
                    contentDescription = "حول التطبيق",
                    tint = TextSecondary,
                    modifier = Modifier.size(22.dp)
                )
            }
        },
        colors = TopAppBarDefaults.topAppBarColors(
            containerColor = DarkSurface,
            titleContentColor = TextPrimary
        )
    )

    if (showAboutDialog) {
        AboutAppDialog(onDismiss = { showAboutDialog = false })
    }
}

@Composable
fun AboutAppDialog(onDismiss: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = DarkSurface,
        title = {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    imageVector = Icons.Default.AutoAwesome,
                    contentDescription = null,
                    tint = AmberAccent,
                    modifier = Modifier.size(22.dp)
                )
                Spacer(modifier = Modifier.width(8.dp))
                Column {
                    Text(
                        text = "SubNova Studio",
                        color = NeonCyan,
                        fontWeight = FontWeight.Bold,
                        fontSize = 17.sp
                    )
                    Text(
                        text = "استوديو سوب نوفا للترجمة الفائقة",
                        color = TextSecondary,
                        fontSize = 11.sp
                    )
                }
            }
        },
        text = {
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                Text(
                    text = "برنامج احترافي متكامل لترجمة وتدقيق وتنقية ملفات الشاشة مع استخراج الترجمة الخام من الفيديو، وحصانة تامة لوسوم ومؤثرات Aegisub.",
                    color = TextPrimary,
                    fontSize = 12.sp,
                    lineHeight = 18.sp
                )

                HorizontalDivider(color = DarkBorder)

                // Developer Rights & Credits Card
                Card(
                    colors = CardDefaults.cardColors(containerColor = DarkCard),
                    shape = RoundedCornerShape(12.dp),
                    border = BorderStroke(1.dp, NeonGreen.copy(alpha = 0.4f)),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(modifier = Modifier.padding(12.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text("👨‍💻 فكرة وتطوير:", color = TextSecondary, fontSize = 11.sp)
                            Spacer(modifier = Modifier.width(6.dp))
                            Text(
                                text = "حاتم الحربي",
                                color = NeonGreen,
                                fontSize = 14.sp,
                                fontWeight = FontWeight.Bold
                            )
                        }
                        Text(
                            text = "Hatim Alharbi",
                            color = TextSecondary,
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Medium
                        )
                        Spacer(modifier = Modifier.height(6.dp))
                        Text(
                            text = "جميع الحقوق محفوظة © 2026 حاتم الحربي",
                            color = AmberAccent,
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }

                Text(
                    text = "الإصدار: 2.0.0 (SubNova Mobile Edition)\nمحرك الذكاء الاصطناعي: دعم كامل لـ Gemini و OpenAI و LM Studio و Ollama.",
                    color = TextSecondary,
                    fontSize = 11.sp,
                    lineHeight = 16.sp
                )
            }
        },
        confirmButton = {
            Button(
                onClick = onDismiss,
                colors = ButtonDefaults.buttonColors(containerColor = NeonCyan, contentColor = Color.Black),
                shape = RoundedCornerShape(8.dp)
            ) {
                Text("إغلاق", fontWeight = FontWeight.Bold)
            }
        }
    )
}

@Composable
fun StatusIndicatorBadge(status: TranslationStatus) {
    val (color, text) = when (status) {
        TranslationStatus.IDLE -> Pair(Color.Gray, "جاهز")
        TranslationStatus.TRANSLATING -> Pair(NeonCyan, "جاري الترجمة...")
        TranslationStatus.IMPROVING -> Pair(AmberAccent, "جاري التحسين...")
        TranslationStatus.PAUSED -> Pair(AmberAccent, "متوقف")
        TranslationStatus.COMPLETED -> Pair(NeonGreen, "مكتمل")
        TranslationStatus.ERROR -> Pair(DangerRed, "خطأ")
    }

    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier
            .clip(CircleShape)
            .background(DarkBorder)
            .padding(horizontal = 8.dp, vertical = 4.dp)
    ) {
        Box(
            modifier = Modifier
                .size(7.dp)
                .clip(CircleShape)
                .background(color)
        )
        Spacer(modifier = Modifier.width(5.dp))
        Text(
            text = text,
            color = TextSecondary,
            fontSize = 10.sp,
            fontWeight = FontWeight.Medium
        )
    }
}

@Composable
fun AppBottomBar(selectedIndex: Int, onSelectTab: (Int) -> Unit) {
    NavigationBar(
        containerColor = DarkSurface,
        tonalElevation = 8.dp
    ) {
        NAV_TABS.forEach { tab ->
            val isSelected = selectedIndex == tab.index
            NavigationBarItem(
                selected = isSelected,
                onClick = { onSelectTab(tab.index) },
                icon = {
                    Icon(
                        imageVector = tab.icon,
                        contentDescription = tab.title,
                        modifier = Modifier.size(22.dp)
                    )
                },
                label = {
                    Text(
                        text = tab.title,
                        fontSize = 11.sp,
                        fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal
                    )
                },
                colors = NavigationBarItemDefaults.colors(
                    selectedIconColor = Color.Black,
                    selectedTextColor = NeonCyan,
                    indicatorColor = NeonCyan,
                    unselectedIconColor = TextSecondary,
                    unselectedTextColor = TextSecondary
                )
            )
        }
    }
}
