import { BadRequestException, Controller, Post, Req, UploadedFile, UseGuards, UseInterceptors } from '@nestjs/common';
import { FileInterceptor } from '@nestjs/platform-express';
import { Request } from 'express';
import { AuthGuard } from '../../auth.guard';
import { UploadService } from './upload.service';

@Controller('uploads')
@UseGuards(AuthGuard)
export class UploadController {
  constructor(private readonly uploads: UploadService) {}
  @Post('photo')
  @UseInterceptors(FileInterceptor('file', { limits: { fileSize: 15 * 1024 * 1024 } }))
  uploadPhoto(@UploadedFile() file: Express.Multer.File, @Req() request: Request) { if (!file) throw new BadRequestException('file is required'); return this.uploads.uploadPhoto(file, (request as any).user.id); }
}
