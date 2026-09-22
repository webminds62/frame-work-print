import { Module } from '@nestjs/common';
import { AuthGuard } from '../../auth.guard';
import { ProdigiClient } from '../../common/prodigi.client';
import { SupabaseService } from '../../supabase.service';
import { FramesController } from './frames.controller';
import { FramesService } from './frames.service';

@Module({ controllers: [FramesController], providers: [FramesService, ProdigiClient, SupabaseService, AuthGuard] })
export class FramesModule {}
