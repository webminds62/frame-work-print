import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { FramesModule } from './modules/frames/frames.module';
import { MockupModule } from './modules/mockup/mockup.module';
import { OrdersModule } from './modules/orders/orders.module';
import { UploadModule } from './modules/upload/upload.module';

@Module({
  imports: [ConfigModule.forRoot({ isGlobal: true }), UploadModule, MockupModule, FramesModule, OrdersModule],
})
export class AppModule {}
})
export class AppModule {}
