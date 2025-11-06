import { ErrorCode } from './error-codes';

export interface ApiResponse<T> {
  code: ErrorCode;
  message: string;
  data: T;
  requestId?: string;
}

export function buildSuccessResponse<T>(data: T, message = 'success', requestId?: string): ApiResponse<T> {
  return {
    code: ErrorCode.OK,
    message,
    data,
    requestId,
  };
}

export function buildErrorResponse<T>(code: ErrorCode, message: string, data: T, requestId?: string): ApiResponse<T> {
  return {
    code,
    message,
    data,
    requestId,
  };
}
