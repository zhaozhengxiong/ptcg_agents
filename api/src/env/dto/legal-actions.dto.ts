import { IsNotEmpty, IsString } from 'class-validator';

export class LegalActionsDto {
  @IsString()
  @IsNotEmpty()
  envId!: string;
}
