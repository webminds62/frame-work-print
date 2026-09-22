import { Injectable, ServiceUnavailableException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';

const FAMILY_MAP: Record<string, [string, Record<string, string>]> = {
  'essential-slim-black': ['GLOBAL-FAP', { color: 'black' }], 'essential-slim-white': ['GLOBAL-FAP', { color: 'white' }],
  'essential-matte-poster': ['GLOBAL-PHO', {}], 'essential-thin-canvas': ['GLOBAL-CAN', { wrap: 'ImageWrap' }],
  'gallery-oak-mat': ['GLOBAL-FAP', { color: 'natural' }], 'gallery-black-mat': ['GLOBAL-FAP', { color: 'black' }],
  'gallery-white-mat': ['GLOBAL-FAP', { color: 'white' }], 'gallery-canvas-wrap': ['GLOBAL-CAN', { wrap: 'ImageWrap' }],
  'gallery-black-floater': ['GLOBAL-CAN', { wrap: 'Black' }], 'atelier-walnut-mat': ['GLOBAL-FAP', { color: 'black' }],
  'atelier-oak-deep': ['GLOBAL-FAP', { color: 'natural' }], 'atelier-black-deep': ['GLOBAL-FAP', { color: 'black' }],
  'atelier-oak-floater': ['GLOBAL-CAN', { wrap: 'ImageWrap' }],
};

export const APPROVED_FRAME_SKUS = new Set([
  'FR-Black-Wood-8x10', 'FR-Black-Wood-11x14', 'FR-White-Wood-8x10', 'FR-Oak-Wood-11x14',
  'FR-Walnut-Wood-11x14', 'FR-Scandi-Oak-16x20', 'FR-Acrylic-Float-11x14',
]);

@Injectable()
export class ProdigiClient {
  constructor(private readonly config: ConfigService) {}
  get baseUrl() { return (this.config.get('PRODIGI_BASE_URL') || 'https://api.sandbox.prodigi.com').replace(/\/$/, ''); }
  get apiKey() { return this.config.get<string>('PRODIGI_API_KEY') || ''; }
  get webhookSecret() { return this.config.get<string>('PRODIGI_WEBHOOK_SECRET') || ''; }

  resolveVariant(id: string) {
    const [familyId, size] = String(id || '').split('__');
    const spec = FAMILY_MAP[familyId];
    return spec && size ? { sku: `${spec[0]}-${size.toUpperCase()}`, attributes: spec[1], familyId, size } : null;
  }

  async request(method: string, endpoint: string, body?: unknown) {
    if (!this.apiKey) throw new ServiceUnavailableException('Prodigi is not configured');
    const response = await fetch(`${this.baseUrl}${endpoint}`, { method, headers: { 'X-API-Key': this.apiKey, 'Content-Type': 'application/json', Accept: 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(`Prodigi returned HTTP ${response.status}`);
    return data;
  }

  product(sku: string) { return this.request('GET', `/v4.0/products/${encodeURIComponent(sku)}`); }
  order(id: string) { return this.request('GET', `/v4.0/Orders/${encodeURIComponent(id)}`); }
  quote(input: { sku: string; copies: number; attributes: Record<string, string>; countryCode: string }) { return this.request('POST', '/v4.0/quotes', { shippingMethod: this.config.get('PRODIGI_DEFAULT_SHIPPING') || 'Budget', destinationCountryCode: input.countryCode || 'US', items: [{ sku: input.sku, copies: Math.max(1, input.copies || 1), attributes: input.attributes, assets: [{ printArea: 'default' }] }] }); }
  createOrder(input: { merchantReference: string; recipient: unknown; sku: string; copies: number; attributes: Record<string, string>; assetUrl: string; shippingMethod?: string; callbackUrl?: string }) { return this.request('POST', '/v4.0/Orders', { merchantReference: input.merchantReference, idempotencyKey: input.merchantReference, shippingMethod: input.shippingMethod || this.config.get('PRODIGI_DEFAULT_SHIPPING') || 'Budget', recipient: input.recipient, callbackUrl: input.callbackUrl, items: [{ sku: input.sku, copies: Math.max(1, input.copies || 1), sizing: 'fillPrintArea', attributes: input.attributes, assets: [{ printArea: 'default', url: input.assetUrl }] }] }); }
  quoteTotals(response: any) { const quote = response.quotes?.[0] || {}; const product = Number(quote.costSummary?.items?.amount || 0); const shipping = Number(quote.costSummary?.shipping?.amount || 0); return { product, shipping, total: product + shipping, currency: quote.costSummary?.items?.currency || 'USD' }; }
}
