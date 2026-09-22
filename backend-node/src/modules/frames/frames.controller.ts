import { Body, Controller, Get, Param, Post, UseGuards } from '@nestjs/common';
import { AuthGuard } from '../../auth.guard';
import { FramesService } from './frames.service';

@Controller()
export class FramesController {
  constructor(private readonly frames: FramesService) {}
  @Get('frames') getFrames() { return this.frames.getFrames(); }
  @Get('frames/:sku') getProductDetails(@Param('sku') sku: string) { return this.frames.getProductDetails(sku); }
  @Get('catalog/store') catalog() { return this.frames.catalog(); }
  @Get('catalog/prodigi/:sku') product(@Param('sku') sku: string) { return this.frames.product(sku); }
  @Get('prodigi/status') status() { return this.frames.status(); }
  @Post('prodigi/quote') @UseGuards(AuthGuard) quote(@Body() body: any) { return this.frames.quote(body); }
}
