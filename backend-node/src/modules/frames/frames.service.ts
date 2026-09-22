import { Injectable, UnprocessableEntityException } from '@nestjs/common';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { APPROVED_FRAME_SKUS, ProdigiClient } from '../../common/prodigi.client';

type FrameProduct = { name: string; sku: string };

const REGULAR_FRAMES: FrameProduct[] = [
  { name: 'Black Modern', sku: 'FR-Black-Wood-8x10' },
  { name: 'Black Modern', sku: 'FR-Black-Wood-11x14' },
  { name: 'White Modern', sku: 'FR-White-Wood-8x10' },
  { name: 'Natural Oak', sku: 'FR-Oak-Wood-11x14' },
];

const UPSCALE_FRAMES: FrameProduct[] = [
  { name: 'Walnut Luxury', sku: 'FR-Walnut-Wood-11x14' },
  { name: 'Scandinavian Oak', sku: 'FR-Scandi-Oak-16x20' },
  { name: 'Floating Acrylic', sku: 'FR-Acrylic-Float-11x14' },
];

@Injectable()
export class FramesService {
  constructor(private readonly prodigi: ProdigiClient) {}
  async getFrames() {
    return {
      regular: REGULAR_FRAMES,
      upscale: UPSCALE_FRAMES,
    };
  }
  async getProductDetails(sku: string) {
    if (!APPROVED_FRAME_SKUS.has(sku)) {
      throw new UnprocessableEntityException('Unknown or unapproved frame SKU');
    }
    return this.prodigi.product(sku);
  }
  async catalog() { const catalog = JSON.parse(await readFile(resolve(process.cwd(), '../backend/catalog/store_catalog.json'), 'utf8')); const variants = catalog.variants.map((variant: any) => { const mapping = this.prodigi.resolveVariant(variant.id); return mapping ? { ...variant, prodigi_sku: mapping.sku, prodigi_attributes: mapping.attributes } : variant; }); return { ...catalog, variants, fulfillment: this.prodigi.apiKey ? 'prodigi' : 'gallery_manual', prodigi_configured: Boolean(this.prodigi.apiKey) }; }
  product(sku: string) { return this.prodigi.product(sku); }
  status() { return { configured: Boolean(this.prodigi.apiKey), base_url: this.prodigi.baseUrl, environment: this.prodigi.baseUrl.includes('sandbox') ? 'sandbox' : 'live', webhook_secret_set: Boolean(this.prodigi.webhookSecret) }; }
  async quote(body: any) { const mapping = this.prodigi.resolveVariant(body.store_variant_id); if (!mapping) throw new Error('Unknown Store variant'); const result = await this.prodigi.quote({ sku: mapping.sku, copies: body.panels || 1, attributes: mapping.attributes, countryCode: body.recipient?.country_code || 'US' }); return { source: 'prodigi', prodigi_sku: mapping.sku, attributes: mapping.attributes, ...this.prodigi.quoteTotals(result) }; }
}
