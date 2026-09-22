package com.frameworksprints.native

import io.ktor.client.HttpClient
import io.ktor.client.call.body
import io.ktor.client.engine.android.Android
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.request.forms.MultiPartFormDataContent
import io.ktor.client.request.forms.formData
import io.ktor.client.request.get
import io.ktor.client.request.post
import io.ktor.client.request.setBody
import io.ktor.http.ContentType
import io.ktor.http.Headers
import io.ktor.http.HttpHeaders
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import io.ktor.serialization.kotlinx.json.json

@Serializable data class UploadResult(val public_id: String, val secure_url: String)
@Serializable data class MockupResult(val mockup_url: String)
@Serializable data class Variant(val id: String, val family_name: String, val size_key: String, val retail_price: Double, val prodigi_sku: String? = null)
@Serializable data class CatalogResult(val variants: List<Variant>)
@Serializable data class OrderResult(val id: String, val prodigi_order_id: String? = null)
@Serializable data class TrackingResult(val stage: String? = null, val tracking_url: String? = null)

class BackendApi(private val baseUrl: String, private val token: String) {
    private val client = HttpClient(Android) { install(ContentNegotiation) { json(Json { ignoreUnknownKeys = true }) } }
    private fun url(path: String) = "$baseUrl/api/$path"
    private fun io.ktor.client.request.HttpRequestBuilder.auth() { headers.append(HttpHeaders.Authorization, "Bearer $token") }

    suspend fun uploadPhoto(bytes: ByteArray): UploadResult = client.post(url("uploads/photo")) {
        suspend fun uploadPhoto(bytes: ByteArray): UploadResult = client.post(url("upload/photo")) {
        auth()
        setBody(MultiPartFormDataContent(formData {
                append("file", bytes, Headers.build {
                append(HttpHeaders.ContentType, ContentType.Image.JPEG.toString())
                append(HttpHeaders.ContentDisposition, "filename=photo.jpg")
            })
        }))
    }.body()

    suspend fun mockup(publicId: String): MockupResult = client.post(url("mockups")) { auth(); setBody(mapOf("public_id" to publicId)) }.body()
    suspend fun catalog(): CatalogResult = client.get(url("catalog/store")).body()
    suspend fun createOrder(variantId: String, assetUrl: String, recipient: Map<String, String>): OrderResult = client.post(url("orders/submit")) { auth(); setBody(mapOf("store_variant_id" to variantId, "asset_url" to assetUrl, "recipient" to recipient, "panels" to 1)) }.body()
    suspend fun tracking(orderId: String): TrackingResult = client.get(url("orders/$orderId/tracking")) { auth() }.body()
}
