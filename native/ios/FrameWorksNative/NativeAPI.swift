import Foundation

struct UploadResult: Codable { let public_id: String; let secure_url: String }
struct MockupResult: Codable { let mockup_url: String }
struct OrderResult: Codable { let id: String }
struct TrackingResult: Codable { let stage: String?; let tracking_url: String? }
struct CatalogResult: Codable { let variants: [StoreVariant] }

struct NativeAPI {
    let baseURL = URL(string: "http://localhost:8000/api")!

    func request(_ path: String, token: String, method: String = "GET", body: Data? = nil, contentType: String = "application/json") async throws -> Data {
        var request = URLRequest(url: baseURL.appending(path: path)); request.httpMethod = method
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue(contentType, forHTTPHeaderField: "Content-Type")
        request.httpBody = body
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else { throw URLError(.badServerResponse) }
        return data
    }

    func uploadPhoto(_ data: Data, token: String) async throws -> UploadResult {
        let boundary = UUID().uuidString
        var body = Data("--\(boundary)\r\nContent-Disposition: form-data; name=\"file\"; filename=\"photo.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n".utf8)
        body.append(data); body.append(Data("\r\n--\(boundary)--\r\n".utf8))
        return try JSONDecoder().decode(UploadResult.self, from: await request("upload/photo", token: token, method: "POST", body: body, contentType: "multipart/form-data; boundary=\(boundary)"))
    }

    func createMockup(publicID: String, token: String) async throws -> MockupResult {
        let body = try JSONSerialization.data(withJSONObject: ["public_id": publicID])
        return try JSONDecoder().decode(MockupResult.self, from: await request("mockups", token: token, method: "POST", body: body))
    }

    func catalog() async throws -> [StoreVariant] {
        let (data, _) = try await URLSession.shared.data(from: baseURL.appending(path: "catalog/store"))
        return try JSONDecoder().decode(CatalogResult.self, from: data).variants
    }

    func createOrder(variantID: String, assetURL: String, recipient: [String: Any], token: String) async throws -> OrderResult {
        let body = try JSONSerialization.data(withJSONObject: ["store_variant_id": variantID, "asset_url": assetURL, "recipient": recipient, "panels": 1])
        return try JSONDecoder().decode(OrderResult.self, from: await request("orders/submit", token: token, method: "POST", body: body))
    }

    func tracking(orderID: String, token: String) async throws -> TrackingResult {
        try JSONDecoder().decode(TrackingResult.self, from: await request("orders/\(orderID)/tracking", token: token))
    }
}
