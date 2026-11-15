package com.subtitlepro.studio.ui.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Cable
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.FormatListBulleted
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.VisibilityOff
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CheckboxDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Divider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.RadioButton
import androidx.compose.material3.RadioButtonDefaults
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.subtitlepro.studio.data.model.ProviderType
import com.subtitlepro.studio.engine.translation.ModelPresets
import com.subtitlepro.studio.ui.theme.AmberAccent
import com.subtitlepro.studio.ui.theme.DarkBorder
import com.subtitlepro.studio.ui.theme.DarkCard
import com.subtitlepro.studio.ui.theme.DarkSurface
import com.subtitlepro.studio.ui.theme.NeonCyan
import com.subtitlepro.studio.ui.theme.NeonGreen
import com.subtitlepro.studio.ui.theme.TextPrimary
import com.subtitlepro.studio.ui.theme.TextSecondary
import com.subtitlepro.studio.viewmodel.MainViewModel

@Composable
fun ProviderSettingsScreen(viewModel: MainViewModel) {
    val config by viewModel.config.collectAsState()
    var isKeyVisible by remember { mutableStateOf(false) }
    var testResultDialog by remember { mutableStateOf<String?>(null) }
    var isTesting by remember { mutableStateOf(false) }

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        // 1. Provider Selector Chips
        item {
            Card(
                colors = CardDefaults.cardColors(containerColor = DarkSurface),
                shape = RoundedCornerShape(16.dp),
                border = BorderStroke(1.dp, DarkBorder),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        text = "🤖 اختيار مزود الذكاء الاصطناعي",
                        color = NeonCyan,
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Bold
                    )
                    Spacer(modifier = Modifier.height(10.dp))

                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        ProviderType.values().forEach { pType ->
                            val isSelected = config.providerType == pType
                            Card(
                                colors = CardDefaults.cardColors(
                                    containerColor = if (isSelected) NeonCyan.copy(alpha = 0.15f) else DarkCard
                                ),
                                shape = RoundedCornerShape(10.dp),
                                border = BorderStroke(
                                    1.dp,
                                    if (isSelected) NeonCyan else DarkBorder
                                ),
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable {
                                        viewModel.updateConfig { providerType = pType }
                                    }
                            ) {
                                Row(
                                    modifier = Modifier.padding(12.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Box(
                                        modifier = Modifier
                                            .size(12.dp)
                                            .clip(RoundedCornerShape(6.dp))
                                            .background(if (isSelected) NeonCyan else DarkBorder)
                                    )
                                    Spacer(modifier = Modifier.width(10.dp))
                                    Text(
                                        text = pType.displayName,
                                        color = if (isSelected) NeonCyan else TextPrimary,
                                        fontSize = 13.sp,
                                        fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }

        // 2. Active Provider Details Configuration
        item {
            Card(
                colors = CardDefaults.cardColors(containerColor = DarkSurface),
                shape = RoundedCornerShape(16.dp),
                border = BorderStroke(1.dp, DarkBorder),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        text = "🔑 إعدادات المزود: ${config.providerType.displayName}",
                        color = TextPrimary,
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Bold
                    )
                    Spacer(modifier = Modifier.height(12.dp))

                    when (config.providerType) {
                        ProviderType.GEMINI -> {
                            // Gemini API Key
                            Text("مفتاح واجهة برمجة تطبيقات Gemini (API Key):", color = TextSecondary, fontSize = 12.sp)
                            Spacer(modifier = Modifier.height(4.dp))
                            OutlinedTextField(
                                value = config.geminiApiKey,
                                onValueChange = { viewModel.updateConfig { geminiApiKey = it } },
                                modifier = Modifier.fillMaxWidth(),
                                placeholder = { Text("AIzaSy...", color = TextSecondary) },
                                singleLine = true,
                                visualTransformation = if (isKeyVisible) VisualTransformation.None else PasswordVisualTransformation(),
                                trailingIcon = {
                                    IconButton(onClick = { isKeyVisible = !isKeyVisible }) {
                                        Icon(
                                            imageVector = if (isKeyVisible) Icons.Default.VisibilityOff else Icons.Default.Visibility,
                                            contentDescription = null,
                                            tint = TextSecondary
                                        )
                                    }
                                },
                                shape = RoundedCornerShape(10.dp),
                                colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = NeonCyan, unfocusedBorderColor = DarkBorder, focusedContainerColor = DarkCard, unfocusedContainerColor = DarkCard)
                            )
                            Spacer(modifier = Modifier.height(12.dp))

                            // Interactive Gemini Model Selector
                            ModelSelectorSection(
                                title = "نموذج Google Gemini المعتمد:",
                                selectedModel = config.geminiModel,
                                presets = ModelPresets.GEMINI,
                                onModelSelected = { viewModel.updateConfig { geminiModel = it } },
                                onFetchModels = { callback ->
                                    viewModel.fetchModelsForCurrentProvider(callback)
                                }
                            )
                        }

                        ProviderType.OPENAI -> {
                            Text("مفتاح واجهة OpenAI (API Key):", color = TextSecondary, fontSize = 12.sp)
                            Spacer(modifier = Modifier.height(4.dp))
                            OutlinedTextField(
                                value = config.openaiApiKey,
                                onValueChange = { viewModel.updateConfig { openaiApiKey = it } },
                                modifier = Modifier.fillMaxWidth(),
                                placeholder = { Text("sk-...", color = TextSecondary) },
                                singleLine = true,
                                visualTransformation = if (isKeyVisible) VisualTransformation.None else PasswordVisualTransformation(),
                                trailingIcon = {
                                    IconButton(onClick = { isKeyVisible = !isKeyVisible }) {
                                        Icon(
                                            imageVector = if (isKeyVisible) Icons.Default.VisibilityOff else Icons.Default.Visibility,
                                            contentDescription = null,
                                            tint = TextSecondary
                                        )
                                    }
                                },
                                shape = RoundedCornerShape(10.dp),
                                colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = NeonCyan, unfocusedBorderColor = DarkBorder, focusedContainerColor = DarkCard, unfocusedContainerColor = DarkCard)
                            )
                            Spacer(modifier = Modifier.height(12.dp))

                            // Interactive OpenAI Model Selector
                            ModelSelectorSection(
                                title = "نموذج OpenAI المعتمد:",
                                selectedModel = config.openaiModel,
                                presets = ModelPresets.OPENAI,
                                onModelSelected = { viewModel.updateConfig { openaiModel = it } },
                                onFetchModels = { callback ->
                                    viewModel.fetchModelsForCurrentProvider(callback)
                                }
                            )
                        }

                        ProviderType.LMSTUDIO -> {
                            Text("عنوان خادم LM Studio (IP:Port):", color = TextSecondary, fontSize = 12.sp)
                            Text("ضع عنوان IP الخاص بحاسوبك على نفس شبكة Wi-Fi، مثال: http://192.168.1.50:1234/v1", color = AmberAccent, fontSize = 10.sp)
                            Spacer(modifier = Modifier.height(4.dp))
                            OutlinedTextField(
                                value = config.lmstudioUrl,
                                onValueChange = { viewModel.updateConfig { lmstudioUrl = it } },
                                modifier = Modifier.fillMaxWidth(),
                                placeholder = { Text("http://192.168.1.100:1234/v1", color = TextSecondary) },
                                singleLine = true,
                                shape = RoundedCornerShape(10.dp),
                                colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = NeonCyan, unfocusedBorderColor = DarkBorder, focusedContainerColor = DarkCard, unfocusedContainerColor = DarkCard)
                            )
                            Spacer(modifier = Modifier.height(12.dp))

                            // Interactive LM Studio Model Selector
                            ModelSelectorSection(
                                title = "نموذج LM Studio المحمل في الخادم:",
                                selectedModel = config.lmstudioModel,
                                presets = ModelPresets.LMSTUDIO,
                                onModelSelected = { viewModel.updateConfig { lmstudioModel = it } },
                                onFetchModels = { callback ->
                                    viewModel.fetchModelsForCurrentProvider(callback)
                                }
                            )
                        }

                        ProviderType.OLLAMA -> {
                            Text("عنوان خادم Ollama (IP:Port):", color = TextSecondary, fontSize = 12.sp)
                            Text("مثال: http://192.168.1.50:11434", color = AmberAccent, fontSize = 10.sp)
                            Spacer(modifier = Modifier.height(4.dp))
                            OutlinedTextField(
                                value = config.ollamaUrl,
                                onValueChange = { viewModel.updateConfig { ollamaUrl = it } },
                                modifier = Modifier.fillMaxWidth(),
                                placeholder = { Text("http://192.168.1.100:11434", color = TextSecondary) },
                                singleLine = true,
                                shape = RoundedCornerShape(10.dp),
                                colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = NeonCyan, unfocusedBorderColor = DarkBorder, focusedContainerColor = DarkCard, unfocusedContainerColor = DarkCard)
                            )
                            Spacer(modifier = Modifier.height(12.dp))

                            // Interactive Ollama Model Selector
                            ModelSelectorSection(
                                title = "نموذج Ollama المعتمد:",
                                selectedModel = config.ollamaModel,
                                presets = ModelPresets.OLLAMA,
                                onModelSelected = { viewModel.updateConfig { ollamaModel = it } },
                                onFetchModels = { callback ->
                                    viewModel.fetchModelsForCurrentProvider(callback)
                                }
                            )
                        }

                        ProviderType.CUSTOM -> {
                            Text("عنوان واجهة الخدمة المخصصة (URL):", color = TextSecondary, fontSize = 12.sp)
                            Spacer(modifier = Modifier.height(4.dp))
                            OutlinedTextField(
                                value = config.customUrl,
                                onValueChange = { viewModel.updateConfig { customUrl = it } },
                                modifier = Modifier.fillMaxWidth(),
                                placeholder = { Text("https://api.openai.com/v1", color = TextSecondary) },
                                singleLine = true,
                                shape = RoundedCornerShape(10.dp),
                                colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = NeonCyan, unfocusedBorderColor = DarkBorder, focusedContainerColor = DarkCard, unfocusedContainerColor = DarkCard)
                            )
                            Spacer(modifier = Modifier.height(10.dp))

                            Text("المفتاح (API Key) (اختياري):", color = TextSecondary, fontSize = 12.sp)
                            Spacer(modifier = Modifier.height(4.dp))
                            OutlinedTextField(
                                value = config.customApiKey,
                                onValueChange = { viewModel.updateConfig { customApiKey = it } },
                                modifier = Modifier.fillMaxWidth(),
                                singleLine = true,
                                visualTransformation = if (isKeyVisible) VisualTransformation.None else PasswordVisualTransformation(),
                                shape = RoundedCornerShape(10.dp),
                                colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = NeonCyan, unfocusedBorderColor = DarkBorder, focusedContainerColor = DarkCard, unfocusedContainerColor = DarkCard)
                            )
                            Spacer(modifier = Modifier.height(12.dp))

                            // Interactive Custom Model Selector
                            ModelSelectorSection(
                                title = "نموذج المزود المخصص:",
                                selectedModel = config.customModel,
                                presets = ModelPresets.CUSTOM,
                                onModelSelected = { viewModel.updateConfig { customModel = it } },
                                onFetchModels = { callback ->
                                    viewModel.fetchModelsForCurrentProvider(callback)
                                }
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(16.dp))

                    // Test Connection Button
                    Button(
                        onClick = {
                            isTesting = true
                            viewModel.testAiConnection { res ->
                                isTesting = false
                                testResultDialog = res
                            }
                        },
                        enabled = !isTesting,
                        colors = ButtonDefaults.buttonColors(containerColor = NeonCyan, contentColor = Color.Black),
                        shape = RoundedCornerShape(10.dp),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Icon(Icons.Default.Cable, contentDescription = null, modifier = Modifier.size(18.dp))
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(if (isTesting) "جاري الاختبار..." else "اختبار الاتصال بالمزود", fontWeight = FontWeight.Bold)
                    }
                }
            }
        }

        // 3. Hyperparameters & Batching Sliders
        item {
            Card(
                colors = CardDefaults.cardColors(containerColor = DarkSurface),
                shape = RoundedCornerShape(16.dp),
                border = BorderStroke(1.dp, DarkBorder),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        text = "🎛️ معاملات التوليد وحجم الدُفعة",
                        color = TextPrimary,
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Bold
                    )
                    Spacer(modifier = Modifier.height(12.dp))

                    // Batch Size
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text("حجم الدفعة (عدد الأسطر لكل طلب):", color = TextSecondary, fontSize = 12.sp)
                        Text("${config.batchSize} سطر", color = NeonCyan, fontWeight = FontWeight.Bold, fontSize = 12.sp)
                    }
                    Slider(
                        value = config.batchSize.toFloat(),
                        onValueChange = { viewModel.updateConfig { batchSize = it.toInt() } },
                        valueRange = 5f..50f,
                        steps = 8,
                        colors = SliderDefaults.colors(thumbColor = NeonCyan, activeTrackColor = NeonCyan)
                    )

                    Spacer(modifier = Modifier.height(8.dp))

                    // Context Previous Lines
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text("أسطر السياق السابقة المرجعية:", color = TextSecondary, fontSize = 12.sp)
                        Text("${config.contextPrevLines} أسطر", color = NeonCyan, fontWeight = FontWeight.Bold, fontSize = 12.sp)
                    }
                    Slider(
                        value = config.contextPrevLines.toFloat(),
                        onValueChange = { viewModel.updateConfig { contextPrevLines = it.toInt() } },
                        valueRange = 0f..8f,
                        steps = 7,
                        colors = SliderDefaults.colors(thumbColor = NeonCyan, activeTrackColor = NeonCyan)
                    )

                    Spacer(modifier = Modifier.height(8.dp))

                    // Temperature
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text("درجة الحرارة (Temperature - الدقة اللفظية):", color = TextSecondary, fontSize = 12.sp)
                        Text("${String.format("%.2f", config.temperature)}", color = NeonCyan, fontWeight = FontWeight.Bold, fontSize = 12.sp)
                    }
                    Slider(
                        value = config.temperature,
                        onValueChange = { viewModel.updateConfig { temperature = it } },
                        valueRange = 0.0f..1.0f,
                        colors = SliderDefaults.colors(thumbColor = NeonCyan, activeTrackColor = NeonCyan)
                    )
                }
            }
        }

        // 4. Smart Auto-Healing Rules
        item {
            Card(
                colors = CardDefaults.cardColors(containerColor = DarkSurface),
                shape = RoundedCornerShape(16.dp),
                border = BorderStroke(1.dp, DarkBorder),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        text = "🛡️ قواعد محرك التنقية الذاتي (Auto-Healing)",
                        color = AmberAccent,
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Bold
                    )
                    Spacer(modifier = Modifier.height(8.dp))

                    HealingCheckboxRow(
                        title = "حصانة وسوم ASS والمؤثرات بنسبة 100%",
                        subtitle = """حماية {\an8} و {\pos} و \N والمؤثرات واستعادتها دون تشويه""",
                        checked = config.protectTags,
                        onChecked = { viewModel.updateConfig { protectTags = it } }
                    )

                    HealingCheckboxRow(
                        title = "ضبط علامات الترقيم العربية",
                        subtitle = "تحويل الفواصل الإنجليزية , إلى ، والاستفهام ? إلى ؟",
                        checked = config.enableArabicPunct,
                        onChecked = { viewModel.updateConfig { enableArabicPunct = it } }
                    )

                    HealingCheckboxRow(
                        title = "تصفية الشوائب اللاتينية وحروف الهلوسة",
                        subtitle = "إزالة الكلمات والضمائر الإنجليزية العالقة مثل \\NI و \\Na",
                        checked = config.enableLatinClean,
                        onChecked = { viewModel.updateConfig { enableLatinClean = it } }
                    )

                    HealingCheckboxRow(
                        title = "معالجة علامات التنصيص اليتيمة",
                        subtitle = "حذف أي أقواس أو علامات تنصيص غير متطابقة في نهاية وبداية الأسطر",
                        checked = config.enableQuoteFix,
                        onChecked = { viewModel.updateConfig { enableQuoteFix = it } }
                    )
                }
            }
        }

        // 5. Developer Rights & Credits Footer Card
        item {
            Card(
                colors = CardDefaults.cardColors(containerColor = DarkSurface),
                shape = RoundedCornerShape(16.dp),
                border = BorderStroke(1.dp, NeonGreen.copy(alpha = 0.35f)),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.AutoAwesome, contentDescription = null, tint = AmberAccent, modifier = Modifier.size(18.dp))
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            text = "SubNova Studio — الإصدار 2.0",
                            color = NeonCyan,
                            fontSize = 14.sp,
                            fontWeight = FontWeight.Bold
                        )
                    }
                    Spacer(modifier = Modifier.height(6.dp))
                    Text(
                        text = "تصميم وبرمجة: حاتم الحربي (Hatim Alharbi)",
                        color = NeonGreen,
                        fontSize = 13.sp,
                        fontWeight = FontWeight.Bold
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = "جميع الحقوق محفوظة © 2026 حاتم الحربي",
                        color = AmberAccent,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Medium
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = "محرك الترجمة والتحسين السينمائي الفائق لملفات الشاشة والفيديو",
                        color = TextSecondary,
                        fontSize = 10.sp
                    )
                }
            }
        }
    }

    if (testResultDialog != null) {
        AlertDialog(
            onDismissRequest = { testResultDialog = null },
            containerColor = DarkSurface,
            title = {
                Text("نتيجة اختبار الاتصال", color = NeonCyan, fontWeight = FontWeight.Bold)
            },
            text = {
                Text(testResultDialog ?: "", color = TextPrimary, fontSize = 13.sp)
            },
            confirmButton = {
                Button(
                    onClick = { testResultDialog = null },
                    colors = ButtonDefaults.buttonColors(containerColor = NeonCyan, contentColor = Color.Black)
                ) {
                    Text("حسناً", fontWeight = FontWeight.Bold)
                }
            }
        )
    }
}

@Composable
fun ModelSelectorSection(
    title: String = "اسم النموذج (Model):",
    selectedModel: String,
    presets: List<String>,
    onModelSelected: (String) -> Unit,
    onFetchModels: ((List<String>) -> Unit) -> Unit
) {
    var showDialog by remember { mutableStateOf(false) }
    var availableModels by remember { mutableStateOf(presets) }
    var isFetching by remember { mutableStateOf(false) }
    var filterText by remember { mutableStateOf("") }

    Column(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(title, color = TextSecondary, fontSize = 12.sp, fontWeight = FontWeight.Bold)

            // Dynamic Fetch button
            TextButton(
                onClick = {
                    isFetching = true
                    onFetchModels { fetched ->
                        isFetching = false
                        if (fetched.isNotEmpty()) {
                            availableModels = fetched
                        }
                        showDialog = true
                    }
                },
                enabled = !isFetching
            ) {
                if (isFetching) {
                    CircularProgressIndicator(modifier = Modifier.size(13.dp), strokeWidth = 2.dp, color = NeonCyan)
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("جاري الفحص...", fontSize = 11.sp, color = NeonCyan)
                } else {
                    Icon(Icons.Default.Refresh, contentDescription = null, modifier = Modifier.size(14.dp), tint = NeonCyan)
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("جلب من المزود 🔄", fontSize = 11.sp, color = NeonCyan, fontWeight = FontWeight.Bold)
                }
            }
        }

        Spacer(modifier = Modifier.height(4.dp))

        // Selected Model Card with "تغيير" button
        Card(
            colors = CardDefaults.cardColors(containerColor = DarkCard),
            shape = RoundedCornerShape(10.dp),
            border = BorderStroke(1.dp, NeonCyan.copy(alpha = 0.5f)),
            modifier = Modifier
                .fillMaxWidth()
                .clickable { showDialog = true }
        ) {
            Row(
                modifier = Modifier.padding(12.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text("النموذج المحدد حالياً:", color = TextSecondary, fontSize = 10.sp)
                    Text(
                        text = selectedModel.ifBlank { "لم يتم اختيار نموذج" },
                        color = NeonCyan,
                        fontSize = 14.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(6.dp))
                        .background(DarkBorder)
                        .padding(horizontal = 8.dp, vertical = 4.dp)
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.FormatListBulleted, contentDescription = null, tint = AmberAccent, modifier = Modifier.size(14.dp))
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("تغيير ▾", color = AmberAccent, fontSize = 11.sp, fontWeight = FontWeight.Bold)
                    }
                }
            }
        }

        Spacer(modifier = Modifier.height(8.dp))

        // Quick Preset Chips
        Text("نماذج سريعة وموصى بها (انقر للتبديل الفوري):", color = TextSecondary, fontSize = 11.sp)
        Spacer(modifier = Modifier.height(4.dp))
        LazyRow(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            items(presets) { modelPreset ->
                val isCurrent = selectedModel == modelPreset
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(8.dp))
                        .background(if (isCurrent) NeonCyan.copy(alpha = 0.2f) else DarkBorder)
                        .border(1.dp, if (isCurrent) NeonCyan else Color.Transparent, RoundedCornerShape(8.dp))
                        .clickable { onModelSelected(modelPreset) }
                        .padding(horizontal = 10.dp, vertical = 6.dp)
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        if (isCurrent) {
                            Icon(Icons.Default.Check, contentDescription = null, tint = NeonCyan, modifier = Modifier.size(12.dp))
                            Spacer(modifier = Modifier.width(4.dp))
                        }
                        Text(
                            text = modelPreset,
                            color = if (isCurrent) NeonCyan else TextPrimary,
                            fontSize = 11.sp,
                            fontWeight = if (isCurrent) FontWeight.Bold else FontWeight.Normal
                        )
                    }
                }
            }
        }

        Spacer(modifier = Modifier.height(8.dp))

        // Custom model text field (manual input)
        OutlinedTextField(
            value = selectedModel,
            onValueChange = onModelSelected,
            modifier = Modifier.fillMaxWidth(),
            placeholder = { Text("أو اكتب اسم النموذج يدوياً هنا...", color = TextSecondary, fontSize = 11.sp) },
            singleLine = true,
            shape = RoundedCornerShape(10.dp),
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = NeonCyan,
                unfocusedBorderColor = DarkBorder,
                focusedContainerColor = DarkCard,
                unfocusedContainerColor = DarkCard
            )
        )
    }

    // Model Selection Dialog
    if (showDialog) {
        AlertDialog(
            onDismissRequest = { showDialog = false },
            containerColor = DarkSurface,
            title = {
                Text("اختر نموذج الذكاء الاصطناعي", color = NeonCyan, fontWeight = FontWeight.Bold, fontSize = 16.sp)
            },
            text = {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(350.dp)
                ) {
                    // Search bar
                    OutlinedTextField(
                        value = filterText,
                        onValueChange = { filterText = it },
                        modifier = Modifier.fillMaxWidth(),
                        placeholder = { Text("بحث في النماذج...", color = TextSecondary, fontSize = 12.sp) },
                        leadingIcon = { Icon(Icons.Default.Search, contentDescription = null, tint = NeonCyan, modifier = Modifier.size(18.dp)) },
                        singleLine = true,
                        shape = RoundedCornerShape(8.dp),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = NeonCyan,
                            unfocusedBorderColor = DarkBorder,
                            focusedContainerColor = DarkCard,
                            unfocusedContainerColor = DarkCard
                        )
                    )

                    Spacer(modifier = Modifier.height(8.dp))

                    val filtered = availableModels.filter {
                        filterText.isBlank() || it.lowercase().contains(filterText.lowercase().trim())
                    }

                    if (filtered.isEmpty()) {
                        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                            Text("لا توجد نماذج مطابقة للبحث", color = TextSecondary, fontSize = 12.sp)
                        }
                    } else {
                        LazyColumn(
                            modifier = Modifier.fillMaxSize(),
                            verticalArrangement = Arrangement.spacedBy(4.dp)
                        ) {
                            items(filtered) { mName ->
                                val isSelected = selectedModel == mName
                                Row(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .clip(RoundedCornerShape(8.dp))
                                        .background(if (isSelected) DarkBorder else Color.Transparent)
                                        .clickable {
                                            onModelSelected(mName)
                                            showDialog = false
                                        }
                                        .padding(horizontal = 8.dp, vertical = 6.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    RadioButton(
                                        selected = isSelected,
                                        onClick = {
                                            onModelSelected(mName)
                                            showDialog = false
                                        },
                                        colors = RadioButtonDefaults.colors(selectedColor = NeonCyan)
                                    )
                                    Spacer(modifier = Modifier.width(6.dp))
                                    Text(
                                        text = mName,
                                        color = if (isSelected) NeonCyan else TextPrimary,
                                        fontSize = 12.sp,
                                        fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal
                                    )
                                }
                            }
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { showDialog = false }) {
                    Text("إغلاق", color = TextSecondary)
                }
            }
        )
    }
}

@Composable
fun HealingCheckboxRow(
    title: String,
    subtitle: String,
    checked: Boolean,
    onChecked: (Boolean) -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onChecked(!checked) }
            .padding(vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Checkbox(
            checked = checked,
            onCheckedChange = onChecked,
            colors = CheckboxDefaults.colors(checkedColor = NeonGreen, checkmarkColor = Color.Black)
        )
        Spacer(modifier = Modifier.width(8.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(title, color = TextPrimary, fontSize = 13.sp, fontWeight = FontWeight.Medium)
            Text(subtitle, color = TextSecondary, fontSize = 10.sp)
        }
    }
}
