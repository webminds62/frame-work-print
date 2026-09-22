import { BadRequestException, Body, Controller, Post, UseGuards } from '@nestjs/common';
import { AuthGuard } from '../../auth.guard';
import { MockupService } from './mockup.service';

@Controller('mockups')
@UseGuards(AuthGuard)
export class MockupController {
  constructor(private readonly mockups: MockupService) {}
  @Post()
  generate(@Body() body: { photo_public_id?: string; frame_public_id?: string; room_public_id?: string }) {
    if (!body.photo_public_id || !body.frame_public_id || !body.room_public_id) {
      throw new BadRequestException('photo_public_id, frame_public_id, and room_public_id are required');
    }
    return this.mockups.generateMockup(body.photo_public_id, body.frame_public_id, body.room_public_id);
  }
}
