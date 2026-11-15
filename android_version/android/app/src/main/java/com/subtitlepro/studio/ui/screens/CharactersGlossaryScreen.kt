package com.subtitlepro.studio.ui.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
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
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
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
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.subtitlepro.studio.data.model.CharacterProfile
import com.subtitlepro.studio.data.model.GlossaryEntry
import com.subtitlepro.studio.ui.theme.AmberAccent
import com.subtitlepro.studio.ui.theme.DangerRed
import com.subtitlepro.studio.ui.theme.DarkBorder
import com.subtitlepro.studio.ui.theme.DarkCard
import com.subtitlepro.studio.ui.theme.DarkSurface
import com.subtitlepro.studio.ui.theme.NeonCyan
import com.subtitlepro.studio.ui.theme.NeonGreen
import com.subtitlepro.studio.ui.theme.TextPrimary
import com.subtitlepro.studio.ui.theme.TextSecondary
import com.subtitlepro.studio.viewmodel.MainViewModel

@Composable
fun CharactersGlossaryScreen(viewModel: MainViewModel) {
    val anime by viewModel.animeMetadata.collectAsState()
    val characters by viewModel.characterList.collectAsState()
    val glossary by viewModel.glossaryList.collectAsState()
    val config by viewModel.config.collectAsState()

    var searchQuery by remember { mutableStateOf("") }
    var newSourceTerm by remember { mutableStateOf("") }
    var newTargetTerm by remember { mutableStateOf("") }
    var newNotes by remember { mutableStateOf("") }

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        // 1. Anime Search Card
        item {
            Card(
                colors = CardDefaults.cardColors(containerColor = DarkSurface),
                shape = RoundedCornerShape(16.dp),
                border = BorderStroke(1.dp, DarkBorder),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        text = "🎬 فحص بيانات العمل والشخصيات (AniList)",
                        color = NeonCyan,
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Bold
                    )
                    Spacer(modifier = Modifier.height(10.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        OutlinedTextField(
                            value = searchQuery,
                            onValueChange = { searchQuery = it },
                            placeholder = { Text("اكتب اسم الأنمي أو العمل بالإنجليزية...", fontSize = 12.sp, color = TextSecondary) },
                            singleLine = true,
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(10.dp),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = NeonCyan,
                                unfocusedBorderColor = DarkBorder,
                                focusedContainerColor = DarkCard,
                                unfocusedContainerColor = DarkCard
                            )
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Button(
                            onClick = { viewModel.searchAnime(searchQuery) },
                            colors = ButtonDefaults.buttonColors(containerColor = NeonCyan, contentColor = Color.Black),
                            shape = RoundedCornerShape(10.dp)
                        ) {
                            Icon(Icons.Default.Search, contentDescription = null, modifier = Modifier.size(18.dp))
                        }
                    }

                    if (anime != null) {
                        Spacer(modifier = Modifier.height(12.dp))
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(8.dp))
                                .background(DarkCard)
                                .padding(10.dp)
                        ) {
                            Column {
                                Text(
                                    text = "${anime?.titleRomaji} (${anime?.titleNative})",
                                    color = NeonGreen,
                                    fontSize = 13.sp,
                                    fontWeight = FontWeight.Bold
                                )
                                Text(
                                    text = "الحلقات: ${anime?.episodes} | تم العثور على ${characters.size} شخصية",
                                    color = TextSecondary,
                                    fontSize = 11.sp
                                )
                            }
                        }
                    }
                }
            }
        }

        // 2. Characters List
        if (characters.isNotEmpty()) {
            item {
                Text(
                    text = "👥 قائمة الشخصيات وأجناسهم",
                    color = TextPrimary,
                    fontSize = 15.sp,
                    fontWeight = FontWeight.Bold
                )
            }

            items(characters, key = { it.id }) { char ->
                CharacterCard(
                    character = char,
                    onUpdate = { updated -> viewModel.updateCharacterProfile(updated) }
                )
            }
        }

        // 3. Story & Scene Notes Card
        item {
            Card(
                colors = CardDefaults.cardColors(containerColor = DarkSurface),
                shape = RoundedCornerShape(16.dp),
                border = BorderStroke(1.dp, DarkBorder),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        text = "📝 ملاحظات وسياق المشاهد (Story Notes)",
                        color = TextPrimary,
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Bold
                    )
                    Spacer(modifier = Modifier.height(6.dp))
                    Text(
                        text = "توجيهات إضافية تُحقن في طلب الترجمة لضبط السياق ونبرة الحديث:",
                        color = TextSecondary,
                        fontSize = 11.sp
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    OutlinedTextField(
                        value = config.storyNotes,
                        onValueChange = { viewModel.updateConfig { storyNotes = it } },
                        modifier = Modifier.fillMaxWidth(),
                        minLines = 3,
                        maxLines = 6,
                        placeholder = { Text("مثال: تدور أحداث العمل في اليابان الإقطاعية، الشخصيات تتحدث بأدب رفيع...", color = TextSecondary, fontSize = 12.sp) },
                        shape = RoundedCornerShape(10.dp),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = NeonCyan,
                            unfocusedBorderColor = DarkBorder,
                            focusedContainerColor = DarkCard,
                            unfocusedContainerColor = DarkCard
                        )
                    )
                }
            }
        }

        // 4. Glossary Manager Card
        item {
            Card(
                colors = CardDefaults.cardColors(containerColor = DarkSurface),
                shape = RoundedCornerShape(16.dp),
                border = BorderStroke(1.dp, DarkBorder),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        text = "📖 قاموس المصطلحات والمفردات الثابتة (Glossary)",
                        color = AmberAccent,
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Bold
                    )
                    Spacer(modifier = Modifier.height(10.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        OutlinedTextField(
                            value = newSourceTerm,
                            onValueChange = { newSourceTerm = it },
                            placeholder = { Text("المصطلح الأصلي", fontSize = 11.sp, color = TextSecondary) },
                            singleLine = true,
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(8.dp),
                            colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = AmberAccent, unfocusedBorderColor = DarkBorder, focusedContainerColor = DarkCard, unfocusedContainerColor = DarkCard)
                        )
                        OutlinedTextField(
                            value = newTargetTerm,
                            onValueChange = { newTargetTerm = it },
                            placeholder = { Text("المقابل العربي", fontSize = 11.sp, color = TextSecondary) },
                            singleLine = true,
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(8.dp),
                            colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = AmberAccent, unfocusedBorderColor = DarkBorder, focusedContainerColor = DarkCard, unfocusedContainerColor = DarkCard)
                        )
                    }

                    Spacer(modifier = Modifier.height(8.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        OutlinedTextField(
                            value = newNotes,
                            onValueChange = { newNotes = it },
                            placeholder = { Text("ملاحظة استخدام (اختياري)", fontSize = 11.sp, color = TextSecondary) },
                            singleLine = true,
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(8.dp),
                            colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = AmberAccent, unfocusedBorderColor = DarkBorder, focusedContainerColor = DarkCard, unfocusedContainerColor = DarkCard)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Button(
                            onClick = {
                                viewModel.addGlossaryTerm(newSourceTerm, newTargetTerm, newNotes)
                                newSourceTerm = ""
                                newTargetTerm = ""
                                newNotes = ""
                            },
                            colors = ButtonDefaults.buttonColors(containerColor = AmberAccent, contentColor = Color.Black),
                            shape = RoundedCornerShape(8.dp)
                        ) {
                            Icon(Icons.Default.Add, contentDescription = null, modifier = Modifier.size(18.dp))
                        }
                    }

                    if (glossary.isNotEmpty()) {
                        Spacer(modifier = Modifier.height(12.dp))
                        HorizontalDivider(color = DarkBorder)
                        Spacer(modifier = Modifier.height(8.dp))

                        glossary.forEach { entry ->
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = 4.dp),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(
                                        text = "${entry.sourceTerm} ➔ ${entry.targetTerm}",
                                        color = TextPrimary,
                                        fontSize = 13.sp,
                                        fontWeight = FontWeight.Medium
                                    )
                                    if (entry.notes.isNotBlank()) {
                                        Text(text = "(${entry.notes})", color = TextSecondary, fontSize = 11.sp)
                                    }
                                }
                                IconButton(
                                    onClick = { viewModel.removeGlossaryTerm(entry) },
                                    modifier = Modifier.size(24.dp)
                                ) {
                                    Icon(Icons.Default.Delete, contentDescription = null, tint = DangerRed, modifier = Modifier.size(16.dp))
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun CharacterCard(
    character: CharacterProfile,
    onUpdate: (CharacterProfile) -> Unit
) {
    var arabicName by remember { mutableStateOf(character.arabicName) }

    Card(
        colors = CardDefaults.cardColors(containerColor = DarkCard),
        shape = RoundedCornerShape(12.dp),
        border = BorderStroke(1.dp, DarkBorder),
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = character.canonicalName,
                        color = TextPrimary,
                        fontSize = 14.sp,
                        fontWeight = FontWeight.Bold
                    )
                    if (character.nativeName.isNotBlank() || character.voiceActor.isNotBlank()) {
                        Text(
                            text = "${character.nativeName} | مؤدي الصوت: ${character.voiceActor}",
                            color = TextSecondary,
                            fontSize = 11.sp
                        )
                    }
                }

                // Gender Badge Toggle
                val isMale = character.gender.equals("MALE", ignoreCase = true)
                val isFemale = character.gender.equals("FEMALE", ignoreCase = true)

                Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(6.dp))
                            .background(if (isMale) NeonCyan else DarkBorder)
                            .clickable {
                                onUpdate(character.copy(gender = "MALE"))
                            }
                            .padding(horizontal = 8.dp, vertical = 4.dp)
                    ) {
                        Text("ذكر", color = if (isMale) Color.Black else TextSecondary, fontSize = 11.sp, fontWeight = FontWeight.Bold)
                    }
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(6.dp))
                            .background(if (isFemale) NeonGreen else DarkBorder)
                            .clickable {
                                onUpdate(character.copy(gender = "FEMALE"))
                            }
                            .padding(horizontal = 8.dp, vertical = 4.dp)
                    ) {
                        Text("أنثى", color = if (isFemale) Color.Black else TextSecondary, fontSize = 11.sp, fontWeight = FontWeight.Bold)
                    }
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            OutlinedTextField(
                value = arabicName,
                onValueChange = {
                    arabicName = it
                    onUpdate(character.copy(arabicName = it))
                },
                placeholder = { Text("الاسم المعتمد بالعربية (مثال: كاوري)", fontSize = 11.sp, color = TextSecondary) },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(8.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = NeonCyan,
                    unfocusedBorderColor = DarkBorder,
                    focusedContainerColor = DarkSurface,
                    unfocusedContainerColor = DarkSurface
                )
            )
        }
    }
}
