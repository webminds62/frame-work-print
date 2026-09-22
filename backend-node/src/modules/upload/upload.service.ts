import { Injectable } from '@nestjs/common';
import { CloudinaryClient } from '../../common/cloudinary.client';

@Injectable()
export class UploadService {
  constructor(private readonly cloudinary: CloudinaryClient) {}
  async uploadPhoto(file: Express.Multer.File, userId: string) {
    const result = await this.cloudinary.upload(file.buffer, `customer_photos/${userId}`);
    return { public_id: result.public_id, secure_url: result.secure_url, width: result.width, height: result.height };
  }
}
