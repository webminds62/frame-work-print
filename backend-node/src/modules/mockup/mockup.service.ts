import { Injectable } from '@nestjs/common';
import { CloudinaryClient } from '../../common/cloudinary.client';

@Injectable()
export class MockupService {
  constructor(private readonly cloudinary: CloudinaryClient) {}
  generateMockup(photoPublicId: string, framePublicId: string, roomPublicId: string) {
    return { mockup_url: this.cloudinary.roomMockup(photoPublicId, framePublicId, roomPublicId) };
  }
}
