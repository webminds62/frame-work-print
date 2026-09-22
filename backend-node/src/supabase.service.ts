import { Injectable, UnauthorizedException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { createClient, SupabaseClient, User } from '@supabase/supabase-js';
import { Request } from 'express';

@Injectable()
export class SupabaseService {
  readonly admin: SupabaseClient;
  private readonly auth: SupabaseClient;

  constructor(config: ConfigService) {
    const url = config.getOrThrow<string>('SUPABASE_URL');
    this.auth = createClient(url, config.getOrThrow<string>('SUPABASE_ANON_KEY'));
    this.admin = createClient(url, config.getOrThrow<string>('SUPABASE_SERVICE_ROLE_KEY'), { auth: { persistSession: false } });
  }

  async userFromRequest(request: Request): Promise<User> {
    const header = request.headers.authorization || '';
    if (!header.startsWith('Bearer ')) throw new UnauthorizedException('Authentication required');
    const { data, error } = await this.auth.auth.getUser(header.slice(7));
    if (error || !data.user) throw new UnauthorizedException('Invalid authentication token');
    return data.user;
  }
}
