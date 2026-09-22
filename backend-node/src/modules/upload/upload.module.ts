import { Module } from '@nestjs/common';
import { CloudinaryClient } from '../../common/cloudinary.client';
import { AuthGuard } from '../../auth.guard';
import { SupabaseService } from '../../supabase.service';
import { UploadController } from './upload.controller';
import { UploadService } from './upload.service';

@Module({ controllers: [UploadController], providers: [UploadService, CloudinaryClient, SupabaseService, AuthGuard] })
export class UploadModule {}
