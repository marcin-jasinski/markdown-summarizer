import {
  Component,
  OnInit,
  AfterViewInit,
  ChangeDetectionStrategy,
  inject,
  signal,
  ElementRef,
  ViewChild,
} from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { MfSnackbarService } from '../../core/services/mf-snackbar.service';
import {
  LucideAngularModule,
  LUCIDE_ICONS,
  LucideIconProvider,
  ZoomIn,
  ZoomOut,
  Maximize2,
} from 'lucide-angular';
import cytoscape from 'cytoscape';
import { ConceptService } from '../../core/services/concept.service';
import type { ConceptGraphResponse } from '../../core/models/api.models';

interface ConceptNode {
  id: string;
  label: string;
  description?: string;
  lesson_id?: string;
}

interface ConceptRelation {
  id: string;
  type: string;
  target: string;
}

@Component({
  selector: 'app-concept-map',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [LucideAngularModule],
  providers: [
    { provide: LUCIDE_ICONS, multi: true, useValue: new LucideIconProvider({ ZoomIn, ZoomOut, Maximize2 }) },
  ],
  templateUrl: './concept-map.html',
  styleUrl: './concept-map.scss',
})
export class ConceptMapComponent implements OnInit, AfterViewInit {
  @ViewChild('graphContainer', { static: true }) container!: ElementRef<HTMLDivElement>;

  private readonly route = inject(ActivatedRoute);
  private readonly conceptService = inject(ConceptService);
  private readonly snackbarService = inject(MfSnackbarService);

  readonly loading = signal(true);
  readonly nodeCount = signal(0);
  readonly edgeCount = signal(0);
  readonly kbName = signal<string | null>(null);
  readonly selectedNode = signal<ConceptNode | null>(null);
  readonly nodeRelations = signal<ConceptRelation[]>([]);

  private cy?: cytoscape.Core;
  private kbId = '';
  private graphEdges: ConceptGraphResponse['edges'] = [];

  private buildStyles(): cytoscape.StylesheetJson {
    return [
      {
        selector: 'node',
        style: {
          label: 'data(label)',
          'background-color': '#5b4fe9',
          color: '#ffffff',
          'text-valign': 'center',
          'text-halign': 'center',
          'text-wrap': 'wrap',
          'text-max-width': '140px',
          'font-size': '13px',
          'font-weight': 600 as unknown as cytoscape.Css.FontWeight,
          'line-height': 1.3,
          shape: 'round-rectangle',
          width: 170,
          height: 60,
          padding: '14px',
          'min-zoomed-font-size': 4,
          'border-width': 2,
          'border-color': '#8b76f0',
        },
      },
      {
        selector: 'node:selected',
        style: { 'background-color': '#06b6d4', 'border-color': '#67e8f9' },
      },
      {
        selector: 'edge',
        style: {
          label: 'data(label)',
          'font-size': '10px',
          color: '#475569',
          width: 2,
          'line-color': '#a78bfa',
          'target-arrow-color': '#a78bfa',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier',
          'text-background-color': '#f8fafc',
          'text-background-opacity': 0.9,
          'text-background-padding': '3px',
          'text-background-shape': 'round-rectangle',
          'text-rotation': 'autorotate',
        },
      },
    ] as cytoscape.StylesheetJson;
  }

  ngOnInit() {
    this.kbId = this.route.snapshot.paramMap.get('kbId') ?? '';
  }

  ngAfterViewInit() {
    this.loadGraph();
  }

  loadGraph() {
    this.loading.set(true);
    this.conceptService.getGraph(this.kbId).subscribe({
      next: (graph) => this.renderGraph(graph),
      error: (err: Error) => {
        this.snackbarService.show(err.message, 'error');
        this.loading.set(false);
      },
    });
  }

  private renderGraph(graph: ConceptGraphResponse) {
    this.nodeCount.set(graph.concepts.length);
    this.edgeCount.set(graph.edges.length);
    this.graphEdges = graph.edges;
    this.loading.set(false);

    const elements: cytoscape.ElementDefinition[] = [
      ...graph.concepts.map((n) => ({
        data: { id: n.key, label: n.label, description: n.description },
      })),
      ...graph.edges.map((e, i) => ({
        data: {
          id: `e${i}`,
          source: e.source,
          target: e.target,
          // Hide noisy generic relation label; keep specific ones.
          label: e.relation && e.relation !== 'related_to' ? e.relation : '',
        },
      })),
    ];

    const hasEdges = graph.edges.length > 0;
    const layout: cytoscape.LayoutOptions = hasEdges
      ? ({
          name: 'cose',
          animate: false,
          padding: 80,
          nodeRepulsion: (node: cytoscape.NodeSingular) => 4500000,
          idealEdgeLength: (edge: cytoscape.EdgeSingular) => 300,
          edgeElasticity: (edge: cytoscape.EdgeSingular) => 0.45,
          nodeOverlap: 20,
          gravity: 0.25,
          numIter: 3000,
          initialTemp: 1000,
          coolingFactor: 0.99,
          minTemp: 1.0,
          componentSpacing: 120,
          fit: true,
          randomize: true,
        } as cytoscape.LayoutOptions)
      : ({
          name: 'circle',
          animate: false,
          padding: 50,
          spacingFactor: 0.8,
          fit: true,
          avoidOverlap: true,
        } as cytoscape.LayoutOptions);

    this.cy = cytoscape({
      container: this.container.nativeElement,
      elements,
      style: this.buildStyles(),
      layout,
    });
    this.cy.minZoom(0.2);
    this.cy.maxZoom(3.0);

    // Tooltip on hover
    this.cy.on('mouseover', 'node', (evt) => {
      evt.target.style({ 'border-width': 4 });
    });
    this.cy.on('mouseout', 'node', (evt) => {
      evt.target.style({ 'border-width': 2 });
    });

    // Node selection panel
    this.cy.on('tap', 'node', (evt) => {
      const node = evt.target;
      const data = node.data();
      this.selectedNode.set({
        id: data.id,
        label: data.label,
        description: data.description,
        lesson_id: data.lesson_id,
      });
      // Compute relations for selected node
      const relations: ConceptRelation[] = this.graphEdges
        .filter((e) => e.source === data.id)
        .map((e, i) => ({ id: `r${i}`, type: e.relation, target: e.target }));
      this.nodeRelations.set(relations);
    });
  }

  fitView() {
    this.cy?.fit(undefined, 30);
  }

  zoomIn() {
    if (this.cy) this.cy.zoom(this.cy.zoom() * 1.25);
  }

  zoomOut() {
    if (this.cy) this.cy.zoom(this.cy.zoom() * 0.8);
  }
}
