import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { of, throwError } from 'rxjs';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { LoginComponent } from './login';
import { AuthService } from '../../core/services/auth.service';
import { MfSnackbarService } from '../../core/services/mf-snackbar.service';

describe('LoginComponent', () => {
  let component: LoginComponent;
  let fixture: any;
  let authService: any;
  let router: any;
  let snackbarService: any;

  beforeEach(async () => {
    const authServiceMock = {
      login: vi.fn().mockReturnValue(of({ access_token: 'test-token' })),
      register: vi.fn(),
      loadCurrentUser: vi.fn(),
    };
    const routerMock = {
      navigate: vi.fn(),
    };
    const snackbarServiceMock = {
      show: vi.fn(),
    };

    await TestBed.configureTestingModule({
      imports: [LoginComponent],
      providers: [
        { provide: AuthService, useValue: authServiceMock },
        { provide: Router, useValue: routerMock },
        { provide: MfSnackbarService, useValue: snackbarServiceMock },
      ],
    }).compileComponents();

    authService = authServiceMock;
    router = routerMock;
    snackbarService = snackbarServiceMock;

    fixture = TestBed.createComponent(LoginComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should call onSubmit when form is submitted', async () => {
    const onSubmitSpy = vi.spyOn(component, 'onSubmit');

    // Set email and password
    component.email.set('test@example.com');
    component.password.set('password123');
    fixture.detectChanges();

    // Trigger form submission
    const form = fixture.nativeElement.querySelector('form');
    if (form) {
      form.dispatchEvent(new Event('submit', { bubbles: true }));
      fixture.detectChanges();
    }

    await fixture.whenStable();

    // The key test: if form binding works, onSubmit should be called
    expect(onSubmitSpy).toHaveBeenCalled();
  });

  it('should submit login form when email and password are filled (direct call)', async () => {
    // Direct method call test
    const testEmail = 'test@example.com';
    const testPassword = 'password123';

    component.email.set(testEmail);
    component.password.set(testPassword);
    fixture.detectChanges();

    // Call onSubmit directly
    component.onSubmit();

    // Verify that auth.login was called with correct parameters
    expect(authService.login).toHaveBeenCalledWith({
      email: testEmail,
      password: testPassword,
    });

    await fixture.whenStable();

    // Verify navigation to dashboard
    expect(router.navigate).toHaveBeenCalledWith(['/dashboard']);
  });

  it('should not submit if email is empty', () => {
    component.email.set('');
    component.password.set('password');

    component.onSubmit();

    expect(authService.login).not.toHaveBeenCalled();
  });

  it('should not submit if password is empty', () => {
    component.email.set('test@example.com');
    component.password.set('');

    component.onSubmit();

    expect(authService.login).not.toHaveBeenCalled();
  });
});
