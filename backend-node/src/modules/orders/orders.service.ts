import { ConflictException, Injectable, NotFoundException, UnprocessableEntityException } from '@nestjs/common';
import { randomUUID } from 'node:crypto';
import { APPROVED_FRAME_SKUS, ProdigiClient } from '../../common/prodigi.client';
import { SupabaseService } from '../../supabase.service';

@Injectable()
export class OrdersService {
  constructor(private readonly supabase: SupabaseService, private readonly prodigi: ProdigiClient) {}
  async list(userId: string) { const { data, error } = await this.supabase.admin.from('orders').select('*').eq('user_id', userId).order('created_at', { ascending: false }); if (error) throw error; return data; }
  async tracking(id: string, userId: string) { const { data: local } = await this.supabase.admin.from('orders').select('*').eq('id', id).eq('user_id', userId).single(); if (!local) throw new NotFoundException('Order not found'); if (!local.prodigi_order_id) throw new ConflictException('Order has not been submitted to Prodigi'); const response: any = await this.prodigi.order(local.prodigi_order_id); const remote = response.order || response; const shipment = remote.shipments?.[0] || {}; const tracking = shipment.tracking || {}; const stage = remote.status?.stage || local.prodigi_stage; await this.supabase.admin.from('orders').update({ prodigi_stage: stage, tracking_url: tracking.url || null, updated_at: new Date().toISOString() }).eq('id', id); return { local_order_id: id, prodigi_order_id: local.prodigi_order_id, stage, shipments: remote.shipments || [], tracking_url: tracking.url || null }; }
  async submit(body: any, userId: string) {
    const mapping = body.store_variant_id ? this.prodigi.resolveVariant(body.store_variant_id) : null;
    const sku = body.sku || mapping?.sku;
    const assetUrl = body.photoUrl || body.imageUrl || body.asset_url;
    const allowedShipping = new Set(['Budget', 'Standard', 'StandardPlus', 'Express', 'Overnight']);
    const shippingMethod = allowedShipping.has(body.shippingMethod) ? body.shippingMethod : 'Standard';
    const recipient = body.recipient || {
      name: body.name,
      email: body.email,
      phoneNumber: body.phone,
      address: {
        line1: body.address1,
        line2: body.address2 || undefined,
        townOrCity: body.city,
        stateOrCounty: body.state || undefined,
        postalOrZipCode: body.zip,
        countryCode: body.country || 'US',
      },
    };
    if (!sku || !APPROVED_FRAME_SKUS.has(sku)) throw new UnprocessableEntityException('Unknown or unapproved frame SKU');
    if (!assetUrl?.startsWith('https://')) throw new UnprocessableEntityException('A public HTTPS imageUrl is required');
    if (!recipient.name || !recipient.address?.line1 || !recipient.address?.townOrCity || !recipient.address?.postalOrZipCode) throw new UnprocessableEntityException('name, address1, city, and zip are required');
    const merchantReference = randomUUID();
    const { data: local, error } = await this.supabase.admin.from('orders').insert({ user_id: userId, merchant_reference: merchantReference, prodigi_sku: sku, amount: body.amount, currency: body.currency || 'USD', recipient, asset_url: assetUrl, metadata: { store_variant_id: body.store_variant_id, panels: body.panels || 1, shipping_method: shippingMethod } }).select().single();
    if (error) throw error;
    const publicBaseUrl = process.env.PUBLIC_BASE_URL?.replace(/\/$/, '');
    const callback = this.prodigi.webhookSecret && publicBaseUrl ? `${publicBaseUrl}/api/webhooks/prodigi?token=${encodeURIComponent(this.prodigi.webhookSecret)}` : undefined;
    const response: any = await this.prodigi.createOrder({ merchantReference, recipient, sku, copies: body.panels || 1, attributes: mapping?.attributes || {}, assetUrl, shippingMethod, callbackUrl: callback });
    const remote = response.order || response;
    await this.supabase.admin.from('orders').update({ prodigi_order_id: remote.id, prodigi_stage: remote.status?.stage || 'InProgress', status: 'in_production', updated_at: new Date().toISOString() }).eq('id', local.id);
    return { ...local, prodigi_order_id: remote.id };
  }
}
