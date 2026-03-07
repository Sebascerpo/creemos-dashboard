import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { LayoutService } from '../service/layout.service';
import { AuthService } from '../../auth/auth.service';

@Component({
    selector: 'app-topbar',
    standalone: true,
    imports: [RouterModule, CommonModule],
    template: `
    <div class="layout-topbar">
        <div class="layout-topbar-logo-container">
            <button class="layout-menu-button layout-topbar-action" (click)="layoutService.onMenuToggle()">
                <i class="pi pi-bars"></i>
            </button>
            <a class="layout-topbar-logo flex items-center gap-3" routerLink="/e14">
                <img src="assets/CreemosColombiaRec_320.png" alt="CREEMOS" width="320" height="106" class="h-8 w-auto" />
                <div class="hidden sm:flex flex-col leading-tight">

                    <span class="text-xs text-surface-500">Monitoreo Electoral</span>
                </div>
            </a>
        </div>


        <div class="layout-topbar-actions">




            <div class="layout-topbar-menu hidden lg:block">
                <div class="layout-topbar-menu-content">

                    <button type="button" class="layout-topbar-action" routerLink="/perfil">
                        <i class="pi pi-user"></i>
                        <span>Perfil</span>
                    </button>
                </div>
            </div>
        </div>

    </div>`
})
export class AppTopbar {
    constructor(
        public layoutService: LayoutService,
        public auth: AuthService
    ) {}
}
