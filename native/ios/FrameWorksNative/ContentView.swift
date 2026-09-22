import PhotosUI
import SwiftUI

struct StoreVariant: Codable, Identifiable {
    let id: String
    let family_name: String
    let size_key: String
    let image: String?
    let retail_price: Double
    let prodigi_sku: String?
}

@MainActor
final class FlowModel: ObservableObject {
    enum Step { case upload, mockup, selectFrame, order, tracking }
    @Published var step: Step = .upload
    @Published var variants: [StoreVariant] = []
    @Published var selectedVariant: StoreVariant?
    @Published var photoURL: String?
    @Published var mockupURL: String?
    @Published var orderID: String?
    @Published var trackingURL: String?
    @Published var status = ""

    private let api = NativeAPI()

    func upload(_ data: Data, token: String) async {
        do {
            let upload = try await api.uploadPhoto(data, token: token)
            photoURL = upload.secure_url
            mockupURL = try await api.createMockup(publicID: upload.public_id, token: token).mockup_url
            variants = try await api.catalog()
            step = .selectFrame
        } catch { status = error.localizedDescription }
    }

    func choose(_ variant: StoreVariant) {
        selectedVariant = variant
        step = .order
    }

    func placeOrder(token: String, recipient: [String: Any]) async {
        guard let selectedVariant, let photoURL else { return }
        do {
            let order = try await api.createOrder(variantID: selectedVariant.id, assetURL: photoURL, recipient: recipient, token: token)
            orderID = order.id
            step = .tracking
            try await refreshTracking(token: token)
        } catch { status = error.localizedDescription }
    }

    func refreshTracking(token: String) async throws {
        guard let orderID else { return }
        let tracking = try await api.tracking(orderID: orderID, token: token)
        trackingURL = tracking.tracking_url
        status = tracking.stage ?? "Received"
    }
}

struct ContentView: View {
    @StateObject private var model = FlowModel()
    @State private var pickerItem: PhotosPickerItem?
    // Replace with the signed-in Supabase access token from the app's auth layer.
    private let accessToken = "SUPABASE_ACCESS_TOKEN"

    var body: some View {
        NavigationStack {
            VStack(spacing: 20) {
                Text("Frame Works Prints").font(.largeTitle.bold())
                switch model.step {
                case .upload:
                    PhotosPicker(selection: $pickerItem, matching: .images) { Label("Choose a photo", systemImage: "photo") }
                        .onChange(of: pickerItem) { _, item in
                            Task {
                                if let data = try? await item?.loadTransferable(type: Data.self) { await model.upload(data, token: accessToken) }
                            }
                        }
                case .mockup:
                    ProgressView("Preparing room mockup…")
                case .selectFrame:
                    List(model.variants) { variant in
                        Button { model.choose(variant) } label: {
                            VStack(alignment: .leading) { Text(variant.family_name); Text("\(variant.size_key) · $\(variant.retail_price, specifier: "%.2f")") }
                        }
                    }
                case .order:
                    Button("Send order to Prodigi") {
                        Task { await model.placeOrder(token: accessToken, recipient: ["name": "Customer", "address1": "", "city": "", "country_code": "US", "zip": ""]) }
                    }.buttonStyle(.borderedProminent)
                case .tracking:
                    Text("Status: \(model.status)")
                    if let trackingURL, let url = URL(string: trackingURL) { Link("Track shipment", destination: url) }
                    Button("Refresh tracking") { Task { try? await model.refreshTracking(token: accessToken) } }
                }
                if !model.status.isEmpty { Text(model.status).foregroundStyle(.secondary) }
            }.padding().navigationTitle("Print").task { model.step = .upload }
        }
    }
}
