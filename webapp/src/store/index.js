import { createStore } from "vuex";
// import { createLogger } from "vuex";
// import { set } from 'vue'

export default createStore({
  state: {
    all_item_data: {}, // keys: item_ids, vals: objects containing all data
    all_block_data: {},
    all_item_children: {},
    all_item_parents: {},
    all_collection_data: {},
    all_collection_children: {},
    all_collection_parents: {},
    refcode_to_id: {},
    sample_list: null,
    equipment_list: null,
    starting_material_list: null,
    collection_list: null,
    saved_status_items: {},
    saved_status_blocks: {},
    saved_status_collections: {},
    updating: {},
    updatingDelayed: {},
    remoteDirectoryTree: {},
    remoteDirectoryTreeSecondsSinceLastUpdate: null,
    itemGraphData: null,
    remoteDirectoryTreeIsLoading: false,
    fileSelectModalIsOpen: false,
    currentUserDisplayName: null,
    currentUserID: null,
    serverInfo: null,
    blocksInfos: {},
    currentUserIsUnverified: false,
    hasUnverifiedUser: false,
    datatablePaginationSettings: {
      samples: {
        page: 0,
        rows: 20,
      },
      collections: {
        page: 0,
        rows: 20,
      },
      collectionItems: {
        page: 0,
        rows: 20,
      },
      startingMaterials: {
        page: 0,
        rows: 20,
      },
      equipment: {
        page: 0,
        rows: 20,
      },
    },
    block_implementation_errors: {},
  },
  mutations: {
    setServerInfo(state, serverInfo) {
      // set the server metadata
      state.serverInfo = serverInfo;
    },
    setSampleList(state, sampleSummaries) {
      // sampleSummaries is an array of json objects summarizing the available samples
      state.sample_list = sampleSummaries || [];
    },
    setStartingMaterialList(state, startingMaterialSummaries) {
      // startingMaterialSummaries is an array of json objects summarizing the available starting materials
      state.starting_material_list = startingMaterialSummaries || [];
    },
    setCollectionList(state, collectionSummaries) {
      // collectionSummaries is an array of json objects summarizing the available collections
      state.collection_list = collectionSummaries || [];
    },
    setDisplayName(state, displayName) {
      state.currentUserDisplayName = displayName;
    },
    setCurrentUserID(state, userID) {
      state.currentUserID = userID;
    },
    setIsUnverified(state, isUnverified) {
      state.currentUserIsUnverified = isUnverified;
    },
    setEquipmentList(state, equipmentSummaries) {
      // equipmentSummary is an array of json objects summarizing the available samples
      state.equipment_list = equipmentSummaries || [];
    },
    appendToSampleList(state, sampleSummary) {
      // sampleSummary is a json object summarizing the new sample
      if (state.sample_list === null) {
        state.sample_list = [sampleSummary];
      } else {
        state.sample_list.push(sampleSummary);
      }
    },
    prependToSampleList(state, sampleSummary) {
      // sampleSummary is a json object summarizing the new sample
      if (state.sample_list === null) {
        state.sample_list = [sampleSummary];
      } else {
        state.sample_list.unshift(sampleSummary);
      }
    },
    prependToStartingMaterialList(state, itemSummary) {
      // sampleSummary is a json object summarizing the new sample
      if (state.starting_material_list === null) {
        state.starting_material_list = [itemSummary];
      } else {
        state.starting_material_list.unshift(itemSummary);
      }
    },
    prependToEquipmentList(state, equipmentSummary) {
      // sampleSummary is a json object summarizing the new sample
      if (state.equipment_list === null) {
        state.equipment_list = [equipmentSummary];
      } else {
        state.equipment_list.unshift(equipmentSummary);
      }
    },
    prependToCollectionList(state, collectionSummary) {
      // collectionSummary is a json object summarizing the new collection
      if (state.collection_list === null) {
        state.collection_list = [collectionSummary];
      } else {
        state.collection_list.unshift(collectionSummary);
      }
    },
    deleteFromSampleList(state, item_id) {
      if (state.sample_list === null) return;

      const index = state.sample_list.map((e) => e.item_id).indexOf(item_id);
      if (index > -1) {
        state.sample_list.splice(index, 1);
      } else {
        console.log(`deleteFromSampleList couldn't find the item with id ${item_id}`);
      }
    },
    deleteFromStartingMaterialList(state, item_id) {
      if (state.starting_material_list === null) return;

      const index = state.starting_material_list.map((e) => e.item_id).indexOf(item_id);
      if (index > -1) {
        state.starting_material_list.splice(index, 1);
      } else {
        console.log(`deleteFromStartingMaterialList couldn't find the item with id ${item_id}`);
      }
    },
    deleteFromCollectionList(state, collection_summary) {
      if (state.collection_list === null) return;

      const index = state.collection_list
        .map((e) => e.collection_id)
        .indexOf(collection_summary.collection_id);
      if (index > -1) {
        state.collection_list.splice(index, 1);
      } else {
        console.log("deleteFromCollectionList couldn't find the object");
      }
    },
    deleteFromEquipmentList(state, item_id) {
      if (state.equipment_list === null) return;

      const index = state.equipment_list.map((e) => e.item_id).indexOf(item_id);
      if (index > -1) {
        state.equipment_list.splice(index, 1);
      } else {
        console.log(`deleteFromEquipmentList couldn't find the item with id ${item_id}`);
      }
    },
    createItemData(state, payload) {
      // payload should have the following fields:
      // refcode, item_id, item_data, child_items, parent_items
      state.all_item_data[payload.item_id] = payload.item_data;
      state.all_item_children[payload.item_id] = payload.child_items;
      state.all_item_parents[payload.item_id] = payload.parent_items;
      state.saved_status_items[payload.item_id] = true;
      state.refcode_to_id[payload.refcode] = payload.item_id;
    },
    setCollectionData(state, payload) {
      // payload should have the following fields:
      // collection_id, data, child_items
      state.all_collection_data[payload.collection_id] = payload.data;
      state.saved_status_collections[payload.collection_id] = true;
    },
    setCollectionSampleList(state, payload) {
      state.all_collection_children[payload.collection_id] = payload.child_items;
    },
    addFileToSample(state, payload) {
      state.all_item_data[payload.item_id].file_ObjectIds.push(payload.file_id);
      console.log("adding file to sample with:", payload.file_info);
      state.all_item_data[payload.item_id].files.push(payload.file_info);
    },
    removeFileFromSample(state, payload) {
      const { item_id, file_id } = payload;
      const files = state.all_item_data[item_id].files;
      const file_ids = state.all_item_data[item_id].file_ObjectIds;
      const index = files.findIndex((file) => file.immutable_id === file_id);

      if (index > -1) {
        file_ids.splice(index, 1);
        files.splice(index, 1);
      }
    },
    setRemoteDirectoryTree(state, remoteDirectoryTree) {
      state.remoteDirectoryTree = remoteDirectoryTree.data;
    },
    setRemoteDirectoryTreeSecondsSinceLastUpdate(state, secondsSinceLastUpdate) {
      state.remoteDirectoryTreeSecondsSinceLastUpdate = secondsSinceLastUpdate;
    },
    addABlock(state, { item_id, new_block_obj, new_block_insert_index }) {
      // payload: item_id, new_block_obj, new_display_order

      // I should actually throw an error if this fails!
      console.assert(
        item_id == new_block_obj.item_id,
        "The block has a different item_id (%s) than the item_id provided to addABlock (%s)",
        item_id,
        new_block_obj.item_id,
      );
      console.log(`addABlock called with: ${item_id}, ${new_block_obj}, ${new_block_insert_index}`);
      let new_block_id = new_block_obj.block_id;
      state.all_item_data[item_id]["blocks_obj"][new_block_id] = new_block_obj;
      if (new_block_insert_index) {
        state.all_item_data[item_id]["display_order"].splice(
          new_block_insert_index,
          0,
          new_block_id,
        );
      }
      // if new_block_insert_index is None, then block is inserted at the end
      else {
        state.all_item_data[item_id]["display_order"].push(new_block_id);
      }
    },
    updateBlockData(state, payload) {
      // requires the following fields in payload:
      // item_id, block_id, block_data
      // This process should invalidate any existing bokeh plot, which may not be present if the plotting
      // in the new block failed.
      state.all_item_data[payload.item_id]["blocks_obj"][payload.block_id]["bokeh_plot_data"] =
        null;
      Object.assign(
        state.all_item_data[payload.item_id]["blocks_obj"][payload.block_id],
        payload.block_data,
      );
      // if there are no block warnings or errors, make sure they are not in the store
      if (!payload.block_data.errors) {
        delete state.all_item_data[payload.item_id]["blocks_obj"][payload.block_id].errors;
      }
      if (!payload.block_data.warnings) {
        delete state.all_item_data[payload.item_id]["blocks_obj"][payload.block_id].warnings;
      }
      state.saved_status_blocks[payload.block_id] = false;
    },
    updateItemData(state, payload) {
      //requires the following fields in payload:
      // item_id, item_data
      Object.assign(state.all_item_data[payload.item_id], payload.item_data);
      if (payload.item_data.creators && state.saved_status_items[payload.item_id] == true) {
        state.saved_status_items[payload.item_id] = true;
      } else {
        state.saved_status_items[payload.item_id] = false;
      }
    },
    updateCollectionData(state, payload) {
      //requires the following fields in payload:
      // item_id, block_data
      Object.assign(state.all_collection_data[payload.collection_id], payload.block_data);
      state.saved_status_collections[payload.collection_id] = false;
    },
    setItemSaved(state, payload) {
      // requires the following fields in payload:
      // item_id, isSaved
      state.saved_status_items[payload.item_id] = payload.isSaved;
    },
    setBlockSaved(state, payload) {
      // requires the following fields in payload:
      // block_id, isSaved
      state.saved_status_blocks[payload.block_id] = payload.isSaved;
    },
    setSavedCollection(state, payload) {
      // requires the following fields in payload:
      // item_id, isSaved
      state.saved_status_collections[payload.collection_id] = payload.isSaved;
    },
    removeBlockFromDisplay(state, payload) {
      // requires the following fields in payload:
      // item_id, block_id
      var display_order = state.all_item_data[payload.item_id].display_order;
      const index = display_order.indexOf(payload.block_id);
      if (index > -1) {
        display_order.splice(index, 1);
      }
    },
    addFile(state, payload) {
      // requires the following fileds in payload:
      // item_id, filename
      state.all_item_data[payload.item_id].files.push(payload.filename);
    },
    removeFilename(state, payload) {
      // requires the following fields in payload:
      // item_id, filename
      var files = state.all_item_data[payload.item_id].files;
      const index = files.indexOf(payload.filename);
      if (index > -1) {
        files.splice(index, 1);
      }
    },
    swapBlockDisplayOrder(state, payload) {
      // requires the following fields in payload:
      // item_id, index1, index2
      // Swaps index1 and index2 in item_id.display_order
      var display_order = state.all_item_data[payload.item_id].display_order;
      if (payload.index1 < display_order.length && payload.index2 < display_order.length) {
        [display_order[payload.index1], display_order[payload.index2]] = [
          display_order[payload.index2],
          display_order[payload.index1],
        ];
      }
      state.saved_status_items[payload.item_id] = false;
    },
    setBlockUpdating(state, block_id) {
      state.updating[block_id] = true;
      state.updatingDelayed[block_id] = true;
    },
    async setBlockNotUpdating(state, block_id) {
      state.updating[block_id] = false;
      await new Promise((resolve) => setTimeout(resolve, 500));
      state.updatingDelayed[block_id] = false; // delayed by 0.5 s, helpful for some animations
    },
    setFileSelectModalOpenStatus(state, isOpen) {
      state.fileSelectModalIsOpen = isOpen;
    },
    setRemoteDirectoryTreeIsLoading(state, isLoading) {
      state.remoteDirectoryTreeIsLoading = isLoading;
    },
    setItemGraph(state, payload) {
      state.itemGraphData = payload;
    },
    setBlocksInfos(state, blocksInfos) {
      blocksInfos.forEach((info) => {
        state.blocksInfos[info.id] = info;
      });
    },
    updateUnverifiedUserStatus(state, hasUnverified) {
      state.currentUserIsUnverified = hasUnverified;
    },
    updateHasUnverified(state, hasUnverified) {
      state.hasUnverifiedUser = hasUnverified;
    },
    setRows(state, { type, rows }) {
      state.datatablePaginationSettings[type].rows = rows;
    },
    setPage(state, { type, page }) {
      state.datatablePaginationSettings[type].page = page;
    },
    removeItemsFromCollection(state, { collection_id, refcodes }) {
      if (state.all_collection_children[collection_id]) {
        state.all_collection_children[collection_id] = state.all_collection_children[
          collection_id
        ].filter((item) => !refcodes.includes(item.refcode));
      }
    },
    setBlockImplementationError(state, { block_id, hasError }) {
      if (hasError) {
        state.block_implementation_errors[block_id] = true;
      } else {
        delete state.block_implementation_errors[block_id];
      }
    },
  },
  getters: {
    getItem: (state) => (item_id) => {
      return state.all_item_data[item_id];
    },
    getBlockByItemIDandBlockID: (state) => (item_id, block_id) => {
      console.log("getBlockBySampleIDandBlockID called with:", item_id, block_id);
      return state.all_item_data[item_id]["blocks_obj"][block_id];
    },
    getCurrentUserDisplayName(state) {
      return state.currentUserDisplayName;
    },
    getCurrentUserID(state) {
      return state.currentUserID;
    },
    getCurrentUserIsUnverified(state) {
      return state.currentUserIsUnverified;
    },
    getHasUnverifiedUser(state) {
      return state.hasUnverifiedUser;
    },
    getBlocksInfos(state) {
      return Object.values(state.blocksInfos);
    },
  },
  actions: {},
  modules: {},
  // plugins: [createLogger()],
});
