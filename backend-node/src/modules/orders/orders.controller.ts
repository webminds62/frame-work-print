import { Body, Controller, Get, Param, Post, Req, UseGuards } from '@nestjs/common';
import { Request } from 'express';
import { AuthGuard } from '../../auth.guard';
import { OrdersService } from './orders.service';

@Controller('orders')
@UseGuards(AuthGuard)
export class OrdersController {
  constructor(private readonly orders: OrdersService) {}
  @Get() list(@Req() request: Request) { return this.orders.list((request as any).user.id); }
  @Get(':id/tracking') tracking(@Param('id') id: string, @Req() request: Request) { return this.orders.tracking(id, (request as any).user.id); }
  @Post() create(@Body() body: any, @Req() request: Request) { return this.orders.submit(body, (request as any).user.id); }
  @Post('submit') submit(@Body() body: any, @Req() request: Request) { return this.orders.submit(body, (request as any).user.id); }
}
