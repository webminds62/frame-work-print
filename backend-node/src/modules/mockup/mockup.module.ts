import { Module } from '@nestjs/common';
import { CloudinaryClient } from '../../common/cloudinary.client';
import { AuthGuard } from '../../auth.guard';
import { SupabaseService } from '../../supabase.service';
import { MockupController } from './mockup.controller';
import { MockupService } from './mockup.service';

@Module({ controllers: [MockupController], providers: [MockupService, CloudinaryClient, SupabaseService, AuthGuard] })
export class MockupModule {}
