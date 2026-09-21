"""Unit tests for CarbonPilot Workflow Engine and Whole-Workflow Optimizer."""

import unittest
from backend.models.workflow import (
    OptimizationConstraints,
    Workflow,
    WorkflowNode,
)
from backend.engine.dag import (
    CycleError,
    DAGValidationError,
    WorkflowDAG,
)
from backend.engine.optimizer import (
    compute_workflow_metrics,
    optimize_workflow,
)


class TestWorkflowDAG(unittest.TestCase):
    """Tests for graph topology, cycle detection, and parallel scheduling."""

    def test_topological_sort_linear(self):
        nodes = [
            WorkflowNode(id="a", name="Task A", type="retrieval", dependencies=[]),
            WorkflowNode(id="b", name="Task B", type="llm", dependencies=["a"]),
            WorkflowNode(id="c", name="Task C", type="llm", dependencies=["b"]),
        ]
        wf = Workflow(id="linear_wf", name="Linear Workflow", nodes=nodes)
        dag = WorkflowDAG(wf)

        order = dag.get_topological_order()
        self.assertEqual(order, ["a", "b", "c"])
        self.assertEqual(dag.get_root_nodes(), ["a"])
        self.assertEqual(dag.get_leaf_nodes(), ["c"])

    def test_cycle_detection(self):
        nodes = [
            WorkflowNode(id="a", name="Task A", type="retrieval", dependencies=["c"]),
            WorkflowNode(id="b", name="Task B", type="llm", dependencies=["a"]),
            WorkflowNode(id="c", name="Task C", type="llm", dependencies=["b"]),
        ]
        wf = Workflow(id="cyclic_wf", name="Cyclic Workflow", nodes=nodes)
        dag = WorkflowDAG(wf)

        with self.assertRaises(CycleError):
            dag.get_topological_order()

    def test_missing_dependency_raises_validation_error(self):
        nodes = [
            WorkflowNode(id="node1", name="Step 1", type="llm", dependencies=["non_existent"]),
        ]
        wf = Workflow(id="bad_wf", name="Bad Workflow", nodes=nodes)
        with self.assertRaises(DAGValidationError):
            WorkflowDAG(wf)

    def test_duplicate_node_id_raises_validation_error(self):
        nodes = [
            WorkflowNode(id="step1", name="Step 1", type="llm", dependencies=[]),
            WorkflowNode(id="step1", name="Duplicate Step", type="llm", dependencies=[]),
        ]
        wf = Workflow(id="dup_wf", name="Duplicate Node Workflow", nodes=nodes)
        with self.assertRaises(DAGValidationError):
            WorkflowDAG(wf)

    def test_parallel_stages_diamond(self):
        # Diamond DAG:
        #      search
        #     /      \
        # analysis_a  analysis_b
        #     \      /
        #      report
        nodes = [
            WorkflowNode(id="search", name="Search", type="retrieval", dependencies=[]),
            WorkflowNode(id="analysis_a", name="Analysis A", type="llm", dependencies=["search"]),
            WorkflowNode(id="analysis_b", name="Analysis B", type="llm", dependencies=["search"]),
            WorkflowNode(
                id="report",
                name="Report",
                type="llm",
                dependencies=["analysis_a", "analysis_b"],
            ),
        ]
        wf = Workflow(id="diamond_wf", name="Diamond Workflow", nodes=nodes)
        dag = WorkflowDAG(wf)

        stages = dag.get_parallel_stages()
        self.assertEqual(len(stages), 3)
        self.assertEqual(stages[0], ["search"])
        self.assertEqual(stages[1], ["analysis_a", "analysis_b"])
        self.assertEqual(stages[2], ["report"])

        parallel_groups = dag.get_parallel_groups()
        self.assertEqual(parallel_groups, [["analysis_a", "analysis_b"]])
        self.assertTrue(dag.are_independent("analysis_a", "analysis_b"))
        self.assertFalse(dag.are_independent("search", "report"))

    def test_critical_path(self):
        nodes = [
            WorkflowNode(id="a", name="A", type="llm", dependencies=[], estimated_tokens=1000),
            WorkflowNode(id="b1", name="B1", type="llm", dependencies=["a"], estimated_tokens=1000),
            WorkflowNode(id="b2", name="B2", type="llm", dependencies=["a"], estimated_tokens=5000),
            WorkflowNode(id="c", name="C", type="llm", dependencies=["b1", "b2"], estimated_tokens=1000),
        ]
        wf = Workflow(id="cp_wf", name="Critical Path Workflow", nodes=nodes)
        dag = WorkflowDAG(wf)

        path, latency = dag.compute_critical_path()
        # B2 has 5000 tokens, so path through B2 is strictly longer than B1
        self.assertEqual(path, ["a", "b2", "c"])
        self.assertGreater(latency, 0)


class TestOptimizer(unittest.TestCase):
    """Tests for whole-workflow deterministic optimizer rules."""

    def test_prune_duplicate_retrieval(self):
        nodes = [
            WorkflowNode(id="search_1", name="Search Web", type="retrieval", dependencies=[]),
            WorkflowNode(id="search_2", name="Search Web", type="retrieval", dependencies=[]),
            WorkflowNode(id="summarize", name="Summarize", type="llm", dependencies=["search_1", "search_2"]),
        ]
        wf = Workflow(id="dup_retrieval", name="Duplicate Retrieval WF", nodes=nodes)

        result = optimize_workflow(wf)
        self.assertEqual(result["baseline_node_count"], 3)
        self.assertEqual(result["optimized_node_count"], 2)
        self.assertEqual(len(result["removed_nodes"]), 1)
        self.assertEqual(result["removed_nodes"][0]["node_id"], "search_2")

    def test_fuse_linear_compatible_steps(self):
        nodes = [
            WorkflowNode(id="search", name="Search", type="retrieval", dependencies=[]),
            WorkflowNode(
                id="draft",
                name="Draft Analysis",
                type="llm",
                dependencies=["search"],
                estimated_tokens=2000,
            ),
            WorkflowNode(
                id="polish",
                name="Polish Analysis",
                type="llm",
                dependencies=["draft"],
                estimated_tokens=2000,
            ),
        ]
        wf = Workflow(id="linear_fusion_wf", name="Linear Fusion WF", nodes=nodes)

        result = optimize_workflow(wf)
        self.assertEqual(result["baseline_node_count"], 3)
        self.assertEqual(result["optimized_node_count"], 2)  # search + (draft+polish)
        self.assertEqual(len(result["combined_nodes"]), 1)
        self.assertEqual(result["combined_nodes"][0]["merged_nodes"], ["draft", "polish"])
        self.assertGreater(result["estimated_improvement"]["token_reduction_pct"], 0)

    def test_market_research_report_full_flow(self):
        # Scenario from Hackathon requirements
        raw_wf = {
            "id": "market_report",
            "name": "Market Research Report",
            "nodes": [
                {
                    "id": "search",
                    "name": "Search Documents",
                    "type": "retrieval",
                    "dependencies": [],
                    "estimated_tokens": 1500,
                },
                {
                    "id": "summary",
                    "name": "Summarize",
                    "type": "llm",
                    "dependencies": ["search"],
                    "required_quality": 0.90,
                    "estimated_tokens": 2000,
                },
                {
                    "id": "analysis_a",
                    "name": "Competitor Analysis",
                    "type": "llm",
                    "dependencies": ["summary"],
                    "required_quality": 0.95,
                    "estimated_tokens": 2500,
                },
                {
                    "id": "analysis_b",
                    "name": "Financial Analysis",
                    "type": "llm",
                    "dependencies": ["summary"],
                    "required_quality": 0.92,
                    "estimated_tokens": 2500,
                },
                {
                    "id": "report",
                    "name": "Generate Report",
                    "type": "llm",
                    "dependencies": ["analysis_a", "analysis_b"],
                    "required_quality": 0.90,
                    "estimated_tokens": 3000,
                },
            ],
        }

        constraints = {
            "carbon_budget": 5.0,
            "deadline": 60.0,
            "priority_mode": "carbon",
        }

        result = optimize_workflow(raw_wf, constraints)

        self.assertIn("baseline_workflow", result)
        self.assertIn("optimized_workflow", result)
        self.assertEqual(result["baseline_node_count"], 5)
        self.assertIn(["analysis_a", "analysis_b"], result["parallel_groups"])
        
        improvement = result["estimated_improvement"]
        self.assertGreater(improvement["latency_reduction_pct"], 0.0)
        self.assertTrue(len(result["explanations"]) > 0)


if __name__ == "__main__":
    unittest.main()
