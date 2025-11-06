import { IsNotEmpty, IsOptional, IsString } from 'class-validator';

export class StepEnvDto {
  @IsString()
  @IsNotEmpty()
  envId!: string;

  @IsOptional()
  action?: Record<string, unknown>;
}
