<template>
  <div class="form-group">
    <label for="graph-depth-control"> <i class="fa fa-layer-group"></i> Graph Depth </label>
    <div class="d-flex align-items-center">
      <button
        class="btn btn-sm btn-outline-secondary"
        :disabled="currentDepth <= 1"
        @click="decrementDepth"
      >
        <i class="fa fa-minus"></i>
      </button>
      <input
        id="graph-depth-control"
        :value="currentDepth"
        type="number"
        min="1"
        max="10"
        class="form-control form-control-sm mx-2 text-center"
        style="width: 60px"
        @input="updateDepth"
      />
      <button
        class="btn btn-sm btn-outline-secondary"
        :disabled="currentDepth >= maxDepth"
        @click="incrementDepth"
      >
        <i class="fa fa-plus"></i>
      </button>
      <span class="ml-2 small text-muted">
        ({{ currentDepth }} level{{ currentDepth > 1 ? "s" : "" }})
      </span>
    </div>
  </div>
</template>

<script>
export default {
  name: "GraphDepthControl",
  props: {
    modelValue: {
      type: Number,
      default: 1,
    },
    maxDepth: {
      type: Number,
      default: 10,
    },
  },
  emits: ["update:modelValue"],
  computed: {
    currentDepth() {
      return this.modelValue;
    },
  },
  methods: {
    updateDepth(event) {
      const value = parseInt(event.target.value, 10);
      if (!isNaN(value) && value >= 1 && value <= this.maxDepth) {
        this.$emit("update:modelValue", value);
      }
    },
    incrementDepth() {
      if (this.currentDepth < this.maxDepth) {
        this.$emit("update:modelValue", this.currentDepth + 1);
      }
    },
    decrementDepth() {
      if (this.currentDepth > 1) {
        this.$emit("update:modelValue", this.currentDepth - 1);
      }
    },
  },
};
</script>
