package com.frameworksprints.native

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.ui.platform.LocalContext
import kotlinx.coroutines.launch

private enum class Step { Upload, Mockup, SelectFrame, Order, Tracking }

@Composable
fun PrintFlowScreen() {
    var step by remember { mutableStateOf(Step.Upload) }
    var status by remember { mutableStateOf("") }
    var orderId by remember { mutableStateOf<String?>(null) }
    var assetUrl by remember { mutableStateOf<String?>(null) }
    var selectedVariantId by remember { mutableStateOf("gallery-canvas-wrap__18x24") }
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val api = remember { BackendApi("http://10.0.2.2:8000", "SUPABASE_ACCESS_TOKEN") }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        if (uri != null) scope.launch {
            try {
                step = Step.Mockup
                val upload = api.uploadPhoto(context.contentResolver.openInputStream(uri)!!.use { it.readBytes() })
                api.mockup(upload.public_id)
                assetUrl = upload.secure_url
                selectedVariantId = api.catalog().variants.firstOrNull()?.id ?: selectedVariantId
                step = Step.SelectFrame
            } catch (error: Exception) { status = error.message ?: "Upload failed"; step = Step.Upload }
        }
    }
    Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Text("Frame Works Prints", style = androidx.compose.material3.MaterialTheme.typography.headlineMedium)
        when (step) {
            Step.Upload -> Button(onClick = { picker.launch("image/*") }) { Text("Choose a photo") }
            Step.Mockup -> Text("Preparing room mockup…")
            Step.SelectFrame -> Button(onClick = { step = Step.Order }) { Text("Choose Gallery frame") }
            Step.Order -> Button(onClick = {
                scope.launch {
                    try {
                        val order = api.createOrder(selectedVariantId, assetUrl ?: error("Photo upload is required"), mapOf("name" to "Customer", "address1" to "", "city" to "", "country_code" to "US", "zip" to ""))
                        orderId = order.id; step = Step.Tracking; status = api.tracking(order.id).stage ?: "InProgress"
                    } catch (error: Exception) { status = error.message ?: "Order failed" }
                }
            }) { Text("Send order to Prodigi") }
            Step.Tracking -> { Text("Status: $status"); Button(onClick = { scope.launch { orderId?.let { status = api.tracking(it).stage ?: status } } }) { Text("Refresh tracking") } }
        }
        if (status.isNotEmpty()) Text(status)
    }
}
