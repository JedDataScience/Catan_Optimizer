import { describe, expect, it } from 'vitest';
import { formatErrorDetail } from './client';

describe('formatErrorDetail', () => {
  it('turns FastAPI 422 details into one readable line', () => {
    const detail = [
      { loc: ['body', 'board'], msg: 'Value error, resource counts must be ...' },
      { loc: ['body', 'ports'], msg: 'Value error, ports must list 9 slot types' },
    ];
    expect(formatErrorDetail(detail)).toBe('resource counts must be ...; ports must list 9 slot types');
  });

  it('passes plain string details through', () => {
    expect(formatErrorDetail('Not Found')).toBe('Not Found');
  });
});
