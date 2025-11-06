import { IsInt, IsOptional, IsString, Min } from 'class-validator';

export class CreateEnvDto {
  @IsOptional()
  @IsInt()
  @Min(0)
  seed?: number;

  @IsOptional()
  @IsString()
  rulesetVersion?: string;
}
