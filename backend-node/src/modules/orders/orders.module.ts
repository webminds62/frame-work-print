import { Module } from '@nestjs/common';
import { AuthGuard } from '../../auth.guard';
import { ProdigiClient } from '../../common/prodigi.client';
import { SupabaseService } from '../../supabase.service';
import { OrdersController } from './orders.controller';
import { OrdersService } from './orders.service';

@Module({ controllers: [OrdersController], providers: [OrdersService, ProdigiClient, SupabaseService, AuthGuard] })
export class OrdersModule {}
