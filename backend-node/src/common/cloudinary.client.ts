import { BadRequestException, Injectable, ServiceUnavailableException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { UploadApiErrorResponse, UploadApiResponse, v2 as Cloudinary } from 'cloudinary';

@Injectable()
export class CloudinaryClient {
  private readonly configured: boolean;

  constructor(config: ConfigService) {
    const cloudName = config.get<string>('CLOUDINARY_CLOUD_NAME');
    const apiKey = config.get<string>('CLOUDINARY_API_KEY');
    const apiSecret = config.get<string>('CLOUDINARY_API_SECRET');
    this.configured = Boolean(cloudName && apiKey && apiSecret);
    if (this.configured) Cloudinary.config({ cloud_name: cloudName, api_key: apiKey, api_secret: apiSecret, secure: true });
  }

  async upload(buffer: Buffer, folder: string): Promise<UploadApiResponse> {
    this.requireConfigured();
    if (!buffer.length) throw new BadRequestException('Photo is empty');
    return new Promise((resolve, reject) => {
      const stream = Cloudinary.uploader.upload_stream(
        { folder, resource_type: 'image', type: 'upload' },
        (error: UploadApiErrorResponse | undefined, result: UploadApiResponse | undefined) => {
          if (error) return reject(error);
          if (!result) return reject(new Error('Cloudinary returned no upload result'));
          resolve(result);
        },
      );
      stream.end(buffer);
    });
  }

  mockup(publicId: string, backgroundPublicId?: string): string {
    this.requireConfigured();
    if (!publicId?.trim()) throw new BadRequestException('Cloudinary public_id is required');
    const transformation: Record<string, unknown>[] = [{ width: 1400, height: 1400, crop: 'fit', quality: 'auto', fetch_format: 'auto' }];
    if (backgroundPublicId?.trim()) transformation.push({ overlay: backgroundPublicId, gravity: 'center', width: 1000, crop: 'fit' });
    return Cloudinary.url(publicId, { secure: true, transformation });
  }

  roomMockup(photoPublicId: string, framePublicId: string, roomPublicId: string): string {
    this.requireConfigured();
    if (!photoPublicId?.trim() || !framePublicId?.trim() || !roomPublicId?.trim()) {
      throw new BadRequestException('photo, frame, and room Cloudinary public_ids are required');
    }

    return Cloudinary.url(roomPublicId, {
      secure: true,
      transformation: [
        { width: 1600, height: 1200, crop: 'fill' },
        { overlay: photoPublicId, width: 600, height: 450, crop: 'fit', gravity: 'center' },
        { overlay: framePublicId, width: 700, height: 550, crop: 'fit', gravity: 'center' },
        { quality: 'auto', fetch_format: 'auto' },
      ],
    });
  }

  private requireConfigured(): void {
    if (!this.configured) throw new ServiceUnavailableException('Cloudinary is not configured');
  }
}

export default Cloudinary;
